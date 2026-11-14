import { useState } from "react";
import { UserRound } from "lucide-react";
import type { Supervisor } from "@/types/report";

const SIZES = { small: "size-9 rounded-xl", card: "size-12 rounded-2xl", large: "size-24 rounded-[28px]" };

export default function ProfileAvatar({ profile, size = "card" }: { profile: Pick<Supervisor, "name" | "photoUrl">; size?: keyof typeof SIZES }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  return <span className={`inline-flex shrink-0 items-center justify-center overflow-hidden bg-kakao text-ink ${SIZES[size]}`}>
    {profile.photoUrl && failedUrl !== profile.photoUrl ? <img src={profile.photoUrl} alt={`${profile.name} 프로필 사진`} width={256} height={256} onError={() => setFailedUrl(profile.photoUrl)} className="size-full object-cover" /> : <UserRound className="h-1/2 w-1/2" aria-hidden="true" />}
  </span>;
}
