import type { Metadata } from "next";
import { CourseSearch } from "@/components/courses/CourseSearch";

export const metadata: Metadata = { title: "Courses" };

export default function CoursesPage() {
  return <CourseSearch />;
}
