"use client";

import { api, type ChangeAction, type StudentIn, type WhatIfOut } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { Alert, Button, Dialog, Spinner, StatusBadge } from "@/components/ui";

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
      {result.loading && <Spinner label="Re-planning" />}
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
  return (
    <div className="space-y-4 text-sm">
      <div className="rounded-card border border-border p-3">
        <p className="text-text-muted">Graduation</p>
        <p className="mt-1 font-heading text-xl font-bold">
          {data.before_graduation?.label ?? "—"} → {data.after_graduation?.label ?? "—"}
        </p>
        <p className="mt-1">
          {data.terms_later > 0 ? (
            <StatusBadge status="blocked" label={`${data.terms_later} term(s) later`} />
          ) : (
            <StatusBadge status="done" label="No change to graduation" />
          )}
        </p>
      </div>
      {data.shifts.length > 0 ? (
        <div>
          <p className="font-medium">Courses that move</p>
          <table className="mt-1 w-full">
            <thead>
              <tr className="text-start text-text-muted">
                <th scope="col" className="text-start font-normal">
                  Course
                </th>
                <th scope="col" className="text-start font-normal">
                  Before
                </th>
                <th scope="col" className="text-start font-normal">
                  After
                </th>
              </tr>
            </thead>
            <tbody>
              {data.shifts.map((shift) => (
                <tr key={shift.code} className="border-t border-border">
                  <td className="py-1 pe-2">
                    <span className="font-medium">{shift.code}</span> {shift.title}
                  </td>
                  <td className="py-1 pe-2">{shift.before?.label ?? "—"}</td>
                  <td className="py-1">{shift.after?.label ?? "not planned"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p>Nothing else moves.</p>
      )}
      {request.action === "drop" ? (
        <p className="text-text-muted">
          This is a preview. If it happens, update the course&apos;s status in &ldquo;Edit courses and goals&rdquo;
          once grades are posted.
        </p>
      ) : null}
      <div className="flex justify-end gap-2">
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
