import type { ContentStatus, WorkflowAction } from "@/lib/api/types";

/** Mirrors TRANSITIONS in backend/app/content/service.py; the API is authoritative. */
const ACTIONS: Record<ContentStatus, WorkflowAction[]> = {
  draft: ["submit", "archive"],
  in_review: ["publish", "request_changes"],
  published: ["unpublish", "archive"],
  archived: ["restore"],
};

export function availableActions(status: ContentStatus): WorkflowAction[] {
  return ACTIONS[status];
}
