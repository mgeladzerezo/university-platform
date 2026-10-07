import type { components } from "./schema";

type Schemas = components["schemas"];

export type Faculty = Schemas["FacultyOut"];
export type Program = Schemas["ProgramOut"];
export type StaffMember = Schemas["StaffOut"];
export type PublicContent = Schemas["ContentPublic"];
export type EditorialContent = Schemas["ContentEditorial"];
export type ContentInput = Schemas["ContentIn"];
export type ContentKind = Schemas["ContentKind"];
export type ContentStatus = Schemas["ContentStatus"];
export type WorkflowAction = Schemas["WorkflowAction"];
export type WorkflowEvent = Schemas["WorkflowEventOut"];
export type ContactInput = Schemas["ContactIn"];

export type Application = Schemas["ApplicationOut"];
export type ApplicationStatus = Schemas["ApplicationStatus"];
export type ApplicationDocument = Schemas["DocumentOut"];
export type DocumentType = Schemas["DocumentType"];
export type PersonalStep = Schemas["PersonalStep"];
export type EducationStep = Schemas["EducationStep"];
export type UploadTicket = Schemas["UploadTicket"];
export type DownloadLink = Schemas["DownloadLink"];
export type QueueItem = Schemas["QueueItem"];
export type ApplicationSummary = Schemas["ApplicationSummary"];

export type Offering = Schemas["OfferingOut"];
export type Enrollment = Schemas["EnrollmentOut"];
export type TimetableEntry = Schemas["TimetableEntry"];
export type Grade = Schemas["GradeOut"];
export type Announcement = Schemas["AnnouncementOut"];
export type RosterEntry = Schemas["RosterEntry"];
export type GradeValue = Schemas["GradeIn"]["value"];

export type Role =
  | "applicant"
  | "student"
  | "lecturer"
  | "editor"
  | "admissions_officer"
  | "admin";
