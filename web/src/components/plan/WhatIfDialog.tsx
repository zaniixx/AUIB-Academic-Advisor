"use client";

import { api, type ChangeAction, type StudentIn, type WhatIfOut } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { ArrowRightIcon } from "@/components/icons";
import { Alert, Button, Dialog, Skeleton, StatusBadge } from "@/components/ui";

export interface WhatIfRequest {
  code: string;
  action: ChangeAction;
}

/** F1.5: the new graduation term and every course that moves. */
export function WhatIfDialog({
  request,
  student,
  onClose,
  onKeep,
}: {
  request: WhatIfRequest;
  student: StudentIn;
  onClose: () => void;
  onKeep: (code: string, term: string) => void;
}) {
  const key = JSON.stringify({ request, student });
  const result = useAsync<WhatIfOut>(key, () => api.whatIf(student, request.code, request.action));
  const title =
    request.action === "drop" ? `What if I don't pass ${request.code}?` : `What if I delay ${request.code}?`;

  return (
    <Dialog open title={title} onClose={onClose}>
      {result.loading && (
        <div role="status" aria-label="Re-planning" className="space-y-3">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      )}
      {result.error && <Alert tone="error">{result.error}</Alert>}
      {result.data && <Outcome data={result.data} request={request} onKeep={onKeep} onClose={onClose} />}
    </Dialog>
  );
}

function Outcome({
  data,
  request,
  onKeep,
  onClose,
}: {
  data: WhatIfOut;
  request: WhatIfRequest;
  onKeep: (code: string, term: string) => void;
  onClose: () => void;
}) {
  const newTerm = data.shifts.find((shift) => shift.code === request.code)?.after?.label;
  const later = data.terms_later > 0;
  return (
    <div className="space-y-5 text-sm">
      <div
        className={`rounded-xl border p-4 ${later ? "border-status-blocked/30 bg-status-blocked/5" : "border-status-done/30 bg-status-done/5"}`}
      >
        <p className="text-text-muted">Graduation</p>
        <p className="mt-1 flex flex-wrap items-center gap-2 font-heading text-xl font-bold">
          <span>{data.before_graduation?.label ?? "—"}</span>
          <ArrowRightIcon aria-hidden className="h-5 w-5 text-text-muted" />
          <span className={later ? "text-status-blocked" : ""}>{data.after_graduation?.label ?? "—"}</span>
        </p>
        <p className="mt-2">
          {later ? (
            <StatusBadge status="blocked" label={`${data.terms_later} term(s) later`} />
          ) : (
            <StatusBadge status="done" label="No change to graduation" />
          )}
        </p>
      </div>
      {data.shifts.length > 0 ? (
        <div>
          <p className="font-semibold">Courses that move</p>
          <table className="mt-2 w-full">
            <thead>
              <tr className="text-xs text-text-muted">
                <th scope="col" className="pb-1 text-start font-medium">
                  Course
                </th>
                <th scope="col" className="pb-1 text-start font-medium">
                  Before
                </th>
                <th scope="col" className="pb-1 text-start font-medium">
                  After
                </th>
              </tr>
            </thead>
            <tbody>
              {data.shifts.map((shift) => (
                <tr key={shift.code} className="border-t border-border">
                  <td className="py-2 pe-2">
                    <span className="font-semibold">{shift.code}</span> {shift.title}
                  </td>
                  <td className="py-2 pe-2 text-text-muted">{shift.before?.label ?? "—"}</td>
                  <td className="py-2 font-medium">{shift.after?.label ?? "not planned"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p>Nothing else moves.</p>
      )}
      {request.action === "drop" ? (
        <p className="rounded-xl bg-surface-sunken p-3 text-text-muted">
          This is a preview. If it happens, update the course&apos;s status in &ldquo;Edit courses and goals&rdquo;
          once grades are posted.
        </p>
      ) : null}
      <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-4">
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
        {request.action === "delay" && newTerm && (
          <Button onClick={() => onKeep(request.code, newTerm)}>Keep this change</Button>
        )}
      </div>
    </div>
  );
}
