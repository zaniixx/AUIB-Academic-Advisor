import { Suspense } from "react";
import { CourseDetail } from "@/components/courses/CourseDetail";
import { Spinner } from "@/components/ui";

type Params = Promise<{ code: string }>;

export default function CoursePage({ params }: { params: Params }) {
  return (
    <Suspense fallback={<Spinner label="Loading course" />}>
      <Course params={params} />
    </Suspense>
  );
}

async function Course({ params }: { params: Params }) {
  const { code } = await params;
  return <CourseDetail code={decodeURIComponent(code)} />;
}
