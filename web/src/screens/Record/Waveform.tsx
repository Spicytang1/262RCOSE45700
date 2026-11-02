type Props = {
  levels: number[];
};

export default function Waveform({ levels }: Props) {
  return (
    <div className="flex h-24 w-full items-center justify-center gap-[3px]" aria-hidden="true">
      {levels.map((v, i) => (
        <span
          key={i}
          className="h-full w-1 rounded-full bg-kakao transition-transform duration-75"
          style={{ transform: `scaleY(${Math.max(v, 0.06)})` }}
        />
      ))}
    </div>
  );
}
