interface LxusBrainLogoProps {
  className?: string;
  size?: number;
}

export function LxusBrainLogo({ className = "", size = 48 }: LxusBrainLogoProps) {
  const scale = size / 1172;
  const height = 1461 * scale;

  return (
    <svg
      viewBox="0 0 1172.08 1461.12"
      width={size}
      height={height}
      className={className}
      aria-label="LxusBrain Logo"
    >
      <defs>
        <linearGradient id="lg1" x1="293.56" y1="763.76" x2="466.93" y2="905.08" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#00aa98"/>
          <stop offset=".08" stopColor="#08c2ab"/>
          <stop offset=".2" stopColor="#11dcc0"/>
          <stop offset=".32" stopColor="#18efcf"/>
          <stop offset=".44" stopColor="#1cfbd9"/>
          <stop offset=".57" stopColor="#1effdc"/>
          <stop offset=".87" stopColor="#00ffc3"/>
          <stop offset=".99" stopColor="#00ff9c"/>
        </linearGradient>
        <linearGradient id="lg2" x1="5475.83" y1="763.76" x2="5649.21" y2="905.08" gradientTransform="translate(6343.67) rotate(-180) scale(1 -1)" xlinkHref="#lg1"/>
        <linearGradient id="lg3" x1="333.07" y1="1352.85" x2="478.96" y2="1171.56" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#0056aa"/>
          <stop offset=".04" stopColor="#1166b7"/>
          <stop offset=".14" stopColor="#3486d1"/>
          <stop offset=".25" stopColor="#4e9fe5"/>
          <stop offset=".35" stopColor="#61b1f3"/>
          <stop offset=".46" stopColor="#6dbcfc"/>
          <stop offset=".57" stopColor="#71c0ff"/>
          <stop offset=".87" stopColor="#08a5ff"/>
          <stop offset=".99" stopColor="#53dbff"/>
        </linearGradient>
        <linearGradient id="lg4" x1="-63.02" y1="987.65" x2="243.3" y2="1074.36" gradientUnits="userSpaceOnUse">
          <stop offset=".57" stopColor="#71c0ff"/>
          <stop offset=".87" stopColor="#08a5ff"/>
          <stop offset=".99" stopColor="#53dbff"/>
        </linearGradient>
        <linearGradient id="lg5" x1="232.92" y1="1159.12" x2="511.82" y2="1496.48" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#0056aa"/>
          <stop offset=".04" stopColor="#1166b7"/>
          <stop offset=".14" stopColor="#3486d1"/>
          <stop offset=".25" stopColor="#4e9fe5"/>
          <stop offset=".35" stopColor="#61b1f3"/>
          <stop offset=".46" stopColor="#6dbcfc"/>
          <stop offset=".57" stopColor="#71c0ff"/>
          <stop offset=".87" stopColor="#08a5ff"/>
          <stop offset=".99" stopColor="#53dbff"/>
        </linearGradient>
      </defs>
      <g>
        <path fill="url(#lg1)" d="m240.48,792.96l12.91,38c1.65,4.85,5.77,8.43,10.8,9.39l152.98,29.19c5.95,1.13,11.96-1.62,14.98-6.86l28.74-49.84c5.19-9-.71-20.34-11.05-21.26l-194.63-17.35c-10.24-.91-18.03,9-14.72,18.74Z"/>
        <path fill="url(#lg2)" d="m920.92,792.96l-12.91,38c-1.65,4.85-5.77,8.43-10.8,9.39l-152.98,29.19c-5.95,1.13-11.96-1.62-14.98-6.86l-28.74-49.84c-5.19-9,.71-20.34,11.05-21.26l194.63-17.35c10.24-.91,18.03,9,14.72,18.74Z"/>
        <path fill="url(#lg3)" d="m485.18,1461.12l-220.37-326.41,156.07,63.41s16.15,9.67,29.77,54.13c13.62,44.46,46.86,191.68,46.86,191.68,0,0-.61,16.39-12.34,17.19Z"/>
        <path fill="url(#lg4)" d="m180.54,857.69l-41.42,425.84s-27.5-41.26-38.17-81.73S1.53,795.17,1.53,795.17c0,0-4.93-6.29,2.9-21.97,7.83-15.68,135.61,55.24,135.61,55.24,0,0,39,23.88,40.51,29.25Z"/>
        <path fill="url(#lg5)" d="m180.54,857.69s12.52,24.38,15.05,41.26c2.52,16.88,36.69,187.99,58.61,219.45,21.92,31.46,230.97,342.72,230.97,342.72l-298.72-139.55s-37.5-23.67-47.33-38.03c-9.84-14.36,41.42-425.84,41.42-425.84Z"/>
        <path fill="url(#lg3)" d="m485.18,0l-220.37,326.41,156.07-63.41s16.15-9.67,29.77-54.13c13.62-44.46,46.86-191.68,46.86-191.68C497.51,17.19,496.9.79,485.18,0Z"/>
        <path fill="url(#lg4)" d="m180.54,603.43l-41.42-425.84s-27.5,41.26-38.17,81.73C90.28,299.78,1.53,665.95,1.53,665.95c0,0-4.93,6.29,2.9,21.97,7.83,15.68,135.61-55.24,135.61-55.24,0,0,39-23.88,40.51-29.25Z"/>
        <path fill="url(#lg5)" d="m180.54,603.43s12.52-24.38,15.05-41.26c2.52-16.88,36.69-187.99,58.61-219.45C276.13,311.25,485.18,0,485.18,0L186.45,139.55s-37.5,23.67-47.33,38.03c-9.84,14.36,41.42,425.84,41.42,425.84Z"/>
        <path fill="url(#lg3)" d="m686.9,1461.12l220.37-326.41-156.07,63.41s-16.15,9.67-29.77,54.13c-13.62,44.46-46.86,191.68-46.86,191.68,0,0,.61,16.39,12.34,17.19Z"/>
        <path fill="url(#lg4)" d="m991.54,857.69l41.42,425.84s27.5-41.26,38.17-81.73c10.67-40.47,99.41-406.64,99.41-406.64,0,0,4.93-6.29-2.9-21.97-7.83-15.68-135.61,55.24-135.61,55.24,0,0-39,23.88-40.51,29.25Z"/>
        <path fill="url(#lg5)" d="m991.54,857.69s-12.52,24.38-15.05,41.26-36.69,187.99-58.61,219.45c-21.92,31.46-230.97,342.72-230.97,342.72l298.72-139.55s37.5-23.67,47.33-38.03c9.84-14.36-41.42-425.84-41.42-425.84Z"/>
        <path fill="url(#lg3)" d="m686.9,0l220.37,326.41-156.07-63.41s-16.15-9.67-29.77-54.13c-13.62-44.46-46.86-191.68-46.86-191.68,0,0,.61-16.39,12.34-17.19Z"/>
        <path fill="url(#lg4)" d="m991.54,603.43l41.42-425.84s27.5,41.26,38.17,81.73c10.67,40.47,99.41,406.64,99.41,406.64,0,0,4.93,6.29-2.9,21.97-7.83,15.68-135.61-55.24-135.61-55.24,0,0-39-23.88-40.51-29.25Z"/>
        <path fill="url(#lg5)" d="m991.54,603.43s-12.52-24.38-15.05-41.26c-2.52-16.88-36.69-187.99-58.61-219.45C895.95,311.25,686.9,0,686.9,0l298.72,139.55s37.5,23.67,47.33,38.03c9.84,14.36-41.42,425.84-41.42,425.84Z"/>
      </g>
    </svg>
  );
}
