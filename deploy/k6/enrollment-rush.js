// Enrollment rush: many students try to take the last seats of one offering at
// the same moment, as happens when registration opens.
//
// What it checks:
//   - the API never reports more enrolled students than the capacity,
//   - every request gets a definite answer (enrolled / waitlisted / already enrolled),
//   - latency stays acceptable while requests queue on the offering row lock.
//
// Run against a staging environment that has a `k6-students` Keycloak client
// allowed to use the password grant for the load-test accounts:
//
//   k6 run -e BASE_URL=https://staging.ukal.example/api/v1 \
//          -e KEYCLOAK_URL=https://sso.staging.ukal.example -e OFFERING_ID=42 \
//          -e STUDENTS=300 -e STUDENT_PASSWORD=... deploy/k6/enrollment-rush.js

import { check, fail } from "k6";
import http from "k6/http";
import { Counter } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000/api/v1";
const KEYCLOAK_URL = __ENV.KEYCLOAK_URL || "http://localhost:8080";
const REALM = __ENV.REALM || "kalinowo";
const CLIENT_ID = __ENV.CLIENT_ID || "uni-web";
const OFFERING_ID = __ENV.OFFERING_ID || "1";
const STUDENTS = Number(__ENV.STUDENTS || 100);
const PASSWORD = __ENV.STUDENT_PASSWORD || "password";

const enrolled = new Counter("enrolled");
const waitlisted = new Counter("waitlisted");

export const options = {
  scenarios: {
    rush: {
      // One iteration per virtual user: each student clicks "enroll" once.
      executor: "per-vu-iterations",
      vus: STUDENTS,
      iterations: 1,
      maxDuration: "2m",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    "http_req_duration{name:enroll}": ["p(95)<1500"],
    checks: ["rate>0.99"],
  },
};

function login(username) {
  const response = http.post(
    `${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/token`,
    { grant_type: "password", client_id: CLIENT_ID, username, password: PASSWORD },
    { tags: { name: "login" } },
  );
  if (response.status !== 200) fail(`login failed for ${username}: ${response.status}`);
  return response.json("access_token");
}

// Tokens are fetched before the rush so that Keycloak is not what gets measured.
export function setup() {
  const tokens = [];
  for (let i = 1; i <= STUDENTS; i++) tokens.push(login(`loadtest-student-${i}`));
  return { tokens };
}

export default function (data) {
  const headers = { Authorization: `Bearer ${data.tokens[__VU - 1]}` };
  const response = http.post(`${BASE_URL}/academics/offerings/${OFFERING_ID}/enrollment`, null, {
    headers,
    tags: { name: "enroll" },
    // 409 means "already enrolled" on a re-run and is an expected answer.
    responseCallback: http.expectedStatuses(200, 409),
  });

  check(response, { "definite answer": (r) => r.status === 200 || r.status === 409 });
  if (response.status === 200) {
    const status = response.json("status");
    if (status === "enrolled") enrolled.add(1);
    else waitlisted.add(1);
  }
}

export function teardown(data) {
  const headers = { Authorization: `Bearer ${data.tokens[0]}` };
  const offerings = http.get(`${BASE_URL}/academics/offerings`, { headers }).json();
  const offering = offerings.find((item) => String(item.id) === String(OFFERING_ID));
  const consistent = check(offering, {
    "enrolled_count never exceeds capacity": (o) => o.enrolled_count <= o.capacity,
  });
  if (!consistent) fail(`oversubscribed: ${offering.enrolled_count}/${offering.capacity}`);
}
