import { Suspense } from "react";
import { CourseDetail, CourseDetailSkeleton } from "@/components/courses/CourseDetail";

type Params = Promise<{ code: string }>;

export default function CoursePage({ params }: { params: Params }) {
  return (
    <Suspense fallback={<CourseDetailSkeleton />}>
      <Course params={params} />
    </Suspense>
  );
}

async function Course({ params }: { params: Params }) {
  const { code } = await params;
  return <CourseDetail code={decodeURIComponent(code)} />;
}
