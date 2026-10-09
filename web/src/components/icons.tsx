/**
 * Line icons drawn in-house (24px grid, 2px stroke, round ends) so the app needs no icon
 * package. Every icon is decorative (aria-hidden): the text beside it carries the meaning.
 */
import type { ReactNode, SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function icon(name: string, paths: ReactNode) {
  function Icon({ className = "h-5 w-5", ...props }: IconProps) {
    return (
      <svg
        aria-hidden
        focusable="false"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={`shrink-0 ${className}`}
        {...props}
      >
        {paths}
      </svg>
    );
  }
  Icon.displayName = name;
  return Icon;
}

export const GraduationCapIcon = icon(
  "GraduationCapIcon",
  <>
    <path d="M22 9 12 4 2 9l10 5 10-5Z" />
    <path d="M6 11.5V16c0 1.7 2.7 3 6 3s6-1.3 6-3v-4.5" />
    <path d="M22 9v6" />
  </>,
);

export const CalendarIcon = icon(
  "CalendarIcon",
  <>
    <rect x="3" y="4.5" width="18" height="16.5" rx="2.5" />
    <path d="M8 2.5v4M16 2.5v4M3 10h18" />
  </>,
);

export const CalendarCheckIcon = icon(
  "CalendarCheckIcon",
  <>
    <rect x="3" y="4.5" width="18" height="16.5" rx="2.5" />
    <path d="M8 2.5v4M16 2.5v4M3 10h18" />
    <path d="m9 15.5 2 2 4-4" />
  </>,
);

export const BookOpenIcon = icon(
  "BookOpenIcon",
  <>
    <path d="M2 4.5h6a4 4 0 0 1 4 4V21a3 3 0 0 0-3-3H2Z" />
    <path d="M22 4.5h-6a4 4 0 0 0-4 4V21a3 3 0 0 1 3-3h7Z" />
  </>,
);

export const SparklesIcon = icon(
  "SparklesIcon",
  <>
    <path d="M11 3.5 12.9 8.6 18 10.5l-5.1 1.9L11 17.5l-1.9-5.1L4 10.5l5.1-1.9Z" />
    <path d="M19 2.5v4M21 4.5h-4M18 17v3M19.5 18.5h-3" />
  </>,
);

export const ShieldCheckIcon = icon(
  "ShieldCheckIcon",
  <>
    <path d="M12 2.5 20 5.5v6c0 5-3.4 8.6-8 10-4.6-1.4-8-5-8-10v-6Z" />
    <path d="m8.8 12 2.2 2.2 4.2-4.4" />
  </>,
);

export const ClipboardIcon = icon(
  "ClipboardIcon",
  <>
    <rect x="8" y="2" width="8" height="4" rx="1" />
    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
    <path d="M9 12h6M9 16h4" />
  </>,
);

export const ListChecksIcon = icon(
  "ListChecksIcon",
  <>
    <path d="m3 6.5 1.8 1.8L8 5M3 16.5l1.8 1.8L8 15" />
    <path d="M12 6.5h9M12 12h9M12 17.5h9" />
  </>,
);

export const MapIcon = icon(
  "MapIcon",
  <>
    <path d="M9 4 3 6.2v13.8l6-2.2 6 2.2 6-2.2V4l-6 2.2Z" />
    <path d="M9 4v13.8M15 6.2V20" />
  </>,
);

export const RouteIcon = icon(
  "RouteIcon",
  <>
    <circle cx="6" cy="19" r="2.5" />
    <circle cx="18" cy="5" r="2.5" />
    <path d="M8.5 19H17a3.5 3.5 0 0 0 0-7H7a3.5 3.5 0 0 1 0-7h8.5" />
  </>,
);

export const CompassIcon = icon(
  "CompassIcon",
  <>
    <circle cx="12" cy="12" r="9.5" />
    <path d="m15.8 8.2-2.1 5.5-5.5 2.1 2.1-5.5Z" />
  </>,
);

export const NoteIcon = icon(
  "NoteIcon",
  <>
    <path d="M15.5 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8.5Z" />
    <path d="M15 3v6h6M7.5 13h9M7.5 17h6" />
  </>,
);

export const PrinterIcon = icon(
  "PrinterIcon",
  <>
    <path d="M6 9V2.5h12V9" />
    <path d="M6 18H4.5A2.5 2.5 0 0 1 2 15.5v-4A2.5 2.5 0 0 1 4.5 9h15a2.5 2.5 0 0 1 2.5 2.5v4a2.5 2.5 0 0 1-2.5 2.5H18" />
    <rect x="6" y="14" width="12" height="7.5" rx="1" />
  </>,
);

export const PencilIcon = icon(
  "PencilIcon",
  <>
    <path d="M16.5 3.5a2.4 2.4 0 0 1 3.4 3.4L7.5 19.3 3 21l1.7-4.5Z" />
    <path d="m14.5 5.5 4 4" />
  </>,
);

export const TrashIcon = icon(
  "TrashIcon",
  <>
    <path d="M3.5 6h17M9 6V3.5h6V6" />
    <path d="M18.5 6 17.6 19.6a2 2 0 0 1-2 1.9H8.4a2 2 0 0 1-2-1.9L5.5 6" />
    <path d="M10 10.5v6M14 10.5v6" />
  </>,
);

export const ArrowRightIcon = icon(
  "ArrowRightIcon",
  <>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </>,
);

export const ArrowLeftIcon = icon(
  "ArrowLeftIcon",
  <>
    <path d="M19 12H5M11 18l-6-6 6-6" />
  </>,
);

export const ChevronDownIcon = icon("ChevronDownIcon", <path d="m6 9 6 6 6-6" />);

export const ChevronRightIcon = icon("ChevronRightIcon", <path d="m9 6 6 6-6 6" />);

export const InfoIcon = icon(
  "InfoIcon",
  <>
    <circle cx="12" cy="12" r="9.5" />
    <path d="M12 16.5v-5M12 8h.01" />
  </>,
);

export const SearchIcon = icon(
  "SearchIcon",
  <>
    <circle cx="11" cy="11" r="7.5" />
    <path d="m21 21-4.6-4.6" />
  </>,
);

export const TargetIcon = icon(
  "TargetIcon",
  <>
    <circle cx="12" cy="12" r="9.5" />
    <circle cx="12" cy="12" r="5.5" />
    <circle cx="12" cy="12" r="1.5" />
  </>,
);

export const LayersIcon = icon(
  "LayersIcon",
  <>
    <path d="m12 2.5 10 5-10 5-10-5Z" />
    <path d="m2 12 10 5 10-5M2 16.5l10 5 10-5" />
  </>,
);

export const SwapIcon = icon(
  "SwapIcon",
  <>
    <path d="M8 3 4 7l4 4M4 7h16M16 21l4-4-4-4M20 17H4" />
  </>,
);

export const SlidersIcon = icon(
  "SlidersIcon",
  <>
    <path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1.5 14h5M9.5 8h5M17.5 16h5" />
  </>,
);

export const CloseIcon = icon("CloseIcon", <path d="M18 6 6 18M6 6l12 12" />);

export const PlusIcon = icon("PlusIcon", <path d="M12 5v14M5 12h14" />);

export const ClockIcon = icon(
  "ClockIcon",
  <>
    <circle cx="12" cy="12" r="9.5" />
    <path d="M12 6.5V12l3.5 2" />
  </>,
);

export const FlagIcon = icon(
  "FlagIcon",
  <>
    <path d="M4.5 21.5V3.5" />
    <path d="M4.5 4h12l-2.2 4.2 2.2 4.3h-12" />
  </>,
);

export const LightbulbIcon = icon(
  "LightbulbIcon",
  <>
    <path d="M9 18h6M10 21.5h4" />
    <path d="M12 2.5a6.5 6.5 0 0 0-3.8 11.8c.5.4.8 1 .8 1.6V16h6v-.1c0-.6.3-1.2.8-1.6A6.5 6.5 0 0 0 12 2.5Z" />
  </>,
);

export const AwardIcon = icon(
  "AwardIcon",
  <>
    <circle cx="12" cy="8.5" r="6" />
    <path d="m8.6 13.4-1.6 8.1 5-2.8 5 2.8-1.6-8.1" />
  </>,
);

export const TrendingUpIcon = icon(
  "TrendingUpIcon",
  <>
    <path d="m22 7-8.5 8.5-5-5L2 17" />
    <path d="M16 7h6v6" />
  </>,
);

export const RotateIcon = icon(
  "RotateIcon",
  <>
    <path d="M3 12a9 9 0 1 0 2.6-6.4L3 8" />
    <path d="M3 3v5h5" />
  </>,
);

export const ExternalIcon = icon(
  "ExternalIcon",
  <>
    <path d="M14 4h6v6M20 4 10 14" />
    <path d="M19 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h4" />
  </>,
);

export const KeyboardIcon = icon(
  "KeyboardIcon",
  <>
    <rect x="2" y="5" width="20" height="14" rx="2.5" />
    <path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M7 15h10" />
  </>,
);

export const HeartIcon = icon(
  "HeartIcon",
  <path d="M19.5 13.6 12 21l-7.5-7.4A5 5 0 1 1 12 7.1a5 5 0 1 1 7.5 6.5Z" />,
);

export const ChartIcon = icon(
  "ChartIcon",
  <>
    <path d="M3 3v18h18" />
    <path d="M7.5 15.5v2M12 11v6.5M16.5 7v10.5" />
  </>,
);

export const FileIcon = icon(
  "FileIcon",
  <>
    <path d="M14.5 2.5H6.5a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7.5Z" />
    <path d="M14 2.5V8h5.5M8.5 13h7M8.5 17h5" />
  </>,
);

export const DownloadIcon = icon(
  "DownloadIcon",
  <>
    <path d="M12 3.5v12M7 10.5l5 5 5-5" />
    <path d="M4 17.5v1.5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1.5" />
  </>,
);

export const UploadIcon = icon(
  "UploadIcon",
  <>
    <path d="M12 15.5v-12M7 8.5l5-5 5 5" />
    <path d="M4 17.5v1.5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1.5" />
  </>,
);

export const KeyIcon = icon(
  "KeyIcon",
  <>
    <circle cx="7.5" cy="15.5" r="4.5" />
    <path d="m10.7 12.3 9.8-9.8M17 6l3 3M14.5 8.5l2 2" />
  </>,
);

export const EyeOffIcon = icon(
  "EyeOffIcon",
  <>
    <path d="M10.6 5.1A9.7 9.7 0 0 1 12 5c5.5 0 9 5.5 9.5 7a13 13 0 0 1-2.6 3.6M6.3 6.4C3.9 8 2.7 10.6 2.5 12c.5 1.5 4 7 9.5 7a9.6 9.6 0 0 0 4.4-1" />
    <path d="M9.9 10a3 3 0 0 0 4.1 4.1M3 3l18 18" />
  </>,
);

/* Small status glyphs used inside badges (status is always shown with a word too). */

export function CheckIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={className} fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 8.5l3 3 7-7" />
    </svg>
  );
}

export function HalfIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={className}>
      <circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M8 2a6 6 0 010 12z" fill="currentColor" />
    </svg>
  );
}

export function CircleIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="3 2">
      <circle cx="8" cy="8" r="6" />
    </svg>
  );
}

export function CrossIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={className} fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 4l8 8M12 4l-8 8" />
    </svg>
  );
}

export function AlertIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={className} fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M8 2l6.5 11.5h-13z" />
      <path d="M8 6.5v3M8 11.5v.5" />
    </svg>
  );
}

export function LockIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className={className} fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="7" width="10" height="7" rx="1" />
      <path d="M5 7V5a3 3 0 016 0v2" />
    </svg>
  );
}
