import { telegram } from '../services/telegram.js';

const INSTAGRAM_URL = 'https://www.instagram.com/pasta_bar_moalboal/';
const LOCATION_URL = 'https://maps.app.goo.gl/tEWYkGMfmLa6KJmp8';
const openExternal = (url) => (event) => {
  if (telegram.openLink(url)) event.preventDefault();
};

export default function Hero() {
  return (
            <header className="hero">
                <div className="hero-top">
                    <div className="hero-side">
                        <div className="hero-links">
                            <a href={INSTAGRAM_URL} onClick={openExternal(INSTAGRAM_URL)} target="_blank" rel="noopener noreferrer">
                                📷 Instagram
                            </a>
                            <a href={LOCATION_URL} onClick={openExternal(LOCATION_URL)} target="_blank" rel="noopener noreferrer">
                                📍 Location
                            </a>
                        </div>
                        <img src="/we-accept.png" alt="We accept Visa, Mastercard, GCash, Sberbank, Bybit crypto" className="we-accept" />
                    </div>
                    <img src="/logo.png" alt="Pasta Bar" className="logo" />
                </div>
                <h1 className="title">FREE DELIVERY FOR MOALBOAL</h1>
                <p className="subtitle">
                    Free transportation "Hotel - Restaurant - Hotel" when ordering from 5,000 PHP.
                </p>
            </header>

  );
}
