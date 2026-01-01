interface TermiVoxedLogoProps {
  className?: string;
  width?: number;
}

export function TermiVoxedLogo({ className = "", width = 180 }: TermiVoxedLogoProps) {
  const scale = width / 208;
  const height = 175.5 * scale;

  return (
    <svg
      viewBox="0 0 208.07 175.5"
      width={width}
      height={height}
      className={className}
      aria-label="TermiVoxed"
    >
      <defs>
        <style>
          {`
            .tv-stroke { fill: none; stroke: #000; stroke-miterlimit: 10; stroke-width: 3px; }
            .tv-termi { font-family: 'JetBrains Mono', 'Cascadia Mono', monospace; font-size: 47px; }
            .tv-voxed { font-family: 'Press Start 2P', cursive; font-size: 45.3px; fill: #fff; }
            .tv-bg { fill: #fff; }
            .tv-black { fill: #000; }
            .tv-green { fill: #39b54a; }
            .tv-orange { fill: #ff931e; }
            .tv-red { fill: #ed1c24; }
          `}
        </style>
      </defs>
      <g>
        <rect className="tv-bg" x="1.5" y="1.5" width="205.07" height="172.5" rx="12" ry="12"/>
        <g>
          <rect className="tv-black" x="1.6" y="98.72" width="205.07" height="75.06" rx="12" ry="12"/>
          <text className="tv-voxed" transform="translate(22.7 158.56) scale(.72 1)">voxed</text>
        </g>
        <text className="tv-termi" transform="translate(13.66 76.6)">termi</text>
        <rect className="tv-stroke" x="1.5" y="1.5" width="205.07" height="172.5" rx="12" ry="12"/>
        <rect className="tv-black" x="170.13" y="60" width="7.5" height="28.5" transform="translate(248.13 -99.63) rotate(90)"/>
        <circle className="tv-red" cx="14.13" cy="14.5" r="3"/>
        <circle className="tv-orange" cx="25.13" cy="14.5" r="3"/>
        <circle className="tv-green" cx="36.13" cy="14.5" r="3"/>
      </g>
    </svg>
  );
}

export default TermiVoxedLogo;
