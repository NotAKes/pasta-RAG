import { useEffect, useRef } from 'react';

const BannerVideo = ({ src, onError }) => {
    const ref = useRef(null);

    useEffect(() => {
        const v = ref.current;
        if (!v) return;
        v.muted = true;
        v.defaultMuted = true;
        v.setAttribute('muted', '');

        const play = () => v.play().catch(() => {});
        const restart = () => { v.currentTime = 0; play(); };
        // Low-power mode can block autoplay; start on the first touch instead.
        const onTouch = () => { if (v.paused) play(); };

        play();
        v.addEventListener('canplay', play);
        v.addEventListener('ended', restart);
        document.addEventListener('touchstart', onTouch, { passive: true });
        document.addEventListener('visibilitychange', onTouch);
        return () => {
            v.removeEventListener('canplay', play);
            v.removeEventListener('ended', restart);
            document.removeEventListener('touchstart', onTouch);
            document.removeEventListener('visibilitychange', onTouch);
        };
    }, [src]);

    return (
        <video
            ref={ref}
            className="banner-video"
            src={src}
            autoPlay
            muted
            loop
            playsInline
            preload="auto"
            onError={onError}
        />
    );
};


export default BannerVideo;
