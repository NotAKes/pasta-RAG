import React, { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';

const tg = window.Telegram.WebApp;

const INSTAGRAM_URL = 'https://www.instagram.com/pasta_bar_moalboal/';
const LOCATION_URL = 'https://maps.app.goo.gl/tEWYkGMfmLa6KJmp8';

// Inside Telegram a plain link is swallowed by the webview; openLink hands it to the browser/app.
const openExternal = (url) => (e) => {
    if (tg?.initData) {
        e.preventDefault();
        tg.openLink(url);
    }
};

// React doesn't reliably render the `muted` attribute, and iOS / Telegram
// webviews refuse to autoplay unless the video is muted, so it's set by hand.
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

const App = () => {
    const [products, setProducts] = useState([]);
    const [cart, setCart] = useState([]);
    const [loading, setLoading] = useState(true);
    const [orderStatus, setOrderStatus] = useState(null);
    const [bannerUrl, setBannerUrl] = useState(null);

    // 1. Считываем стол из URL (?table=5) или оставляем пустым
    const queryParams = new URLSearchParams(window.location.search);
    const urlTable = queryParams.get('table'); 
    
    const [table, setTable] = useState(urlTable || '');
    const [name, setName] = useState('');
    const [phone, setPhone] = useState('');

    const SECRET_TOKEN = "notakes";

    // 2. Загрузка меню и обработка вложенной структуры metadata
    useEffect(() => {
        tg.ready();
        tg.expand();
        try {
            tg.setHeaderColor('#fbf5ea');
            tg.setBackgroundColor('#fbf5ea');
        } catch { /* older Telegram clients */ }

        const fetchProducts = async () => {
            try {
                const response = await fetch('https://pastamoalboal.shop/api', {
                    headers: { 'Content-Type': 'application/json' }
                });

                if (!response.ok) throw new Error('Failed to fetch menu');

                const rawData = await response.json();
                
                // Выпрямляем данные для удобной работы в React
                const flatData = rawData.map((item, index) => ({
                    id: String(index + 1),
                    name: item.metadata?.dish_name || "Unknown Dish",
                    price: Number(item.metadata?.price) || 0, // Защита от NaN
                    description: item.text?.split('.')[0] || "", 
                    image_url: item.metadata?.image_url || "" 
                }));

                setProducts(flatData);
            } catch (error) {
                console.error("Error:", error);
                tg.showAlert("Error loading menu");
            } finally {
                setLoading(false);
            }
        };

        fetchProducts();

        fetch('https://pastamoalboal.shop/api/banner')
            .then(r => r.ok ? r.json() : null)
            .then(d => setBannerUrl(d?.video_url || null))
            .catch(() => {});

        if (tg.initDataUnsafe?.user?.first_name) {
            setName(tg.initDataUnsafe.user.first_name);
        }
    }, []);

    // 3. Логика корзины
    const onAdd = (product) => {
        const exist = cart.find(x => x.id === product.id);
        if (exist) {
            setCart(cart.map(x => x.id === product.id ? { ...exist, quantity: exist.quantity + 1 } : x));
        } else {
            setCart([...cart, { ...product, quantity: 1 }]);
        }
    };

    const onRemove = (product) => {
        const exist = cart.find(x => x.id === product.id);
        if (exist.quantity === 1) {
            setCart(cart.filter(x => x.id !== product.id));
        } else {
            setCart(cart.map(x => x.id === product.id ? { ...exist, quantity: exist.quantity - 1 } : x));
        }
    };

    const getTotalPrice = () => {
        return cart.reduce((acc, item) => acc + item.price * item.quantity, 0);
    };

    // 4. Отправка заказа (Исправлено: title, id-string, table-string)
    const onCheckout = useCallback(async () => {
        if (cart.length === 0) return;

        if (!table) {
            tg.showAlert("Please enter Table Number!");
            return;
        }

        if (!phone.trim()) {
            tg.showAlert("Please leave any contact (phone, Telegram, WhatsApp...).\n\nIf we can't reach you, your order will be canceled.");
            return;
        }

        setOrderStatus('sending');

        const orderData = {
            user_id: tg.initDataUnsafe?.user?.id || null,
            name: name || "Guest",
            phone: phone || "",
            table: String(table), // Обязательно строка
            items: cart.map(item => ({
                id: String(item.id),
                title: String(item.name), // Поле должно называться title
                price: Number(item.price),
                quantity: Math.min(Number(item.quantity), 20) // Лимит 20
            }))
        };

        try {
            const response = await fetch('https://pastamoalboal.shop/api/create_order', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Secret-Token': SECRET_TOKEN
                },
                body: JSON.stringify(orderData),
            });


            if (response.ok) {
                setOrderStatus('success');
                setTimeout(() => tg.close(), 3000);
            } else {
                throw new Error('Server validation failed');
            }
        } catch (error) {
            setOrderStatus('error');
            tg.showAlert("Connection Error. Please try again.");
        }
    }, [cart, name, phone, table]);

    // 5. Рендеринг
    if (loading) return (
        <div className="loading">
            <img src="/logo.png" alt="" className="logo" />
            Loading menu…
        </div>
    );
    if (orderStatus === 'success') return (
        <div className="success-screen">
            <img src="/logo.png" alt="" className="logo" />
            <h1>Order sent!</h1>
            <p>Delivery to {table}. We'll contact you shortly.</p>
        </div>
    );

    const itemCount = cart.reduce((acc, item) => acc + item.quantity, 0);

    return (
        <div className="App">
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

            {/* Блок контактов и выбора стола */}
            <div className="form-container top-form">
                <h2 className="section-title">Your details</h2>
                <div className="form-row">
                    <input
                        type="text"
                        placeholder="Hotel"
                        value={table}
                        onChange={(e) => setTable(e.target.value)}
                        className="input-field"
                        style={{ width: '30%' }}
                    />
                    <input
                        type="text"
                        placeholder="Name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className="input-field"
                        style={{ width: '70%' }}
                    />
                </div>
                <input
                    type="text"
                    placeholder="Any contact with you *"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className={`input-field ${!phone.trim() ? 'input-required' : ''}`}
                    required
                />
                <p className="contact-warning">
                    ⚠️ Contact is required. If we can't reach you, your order will be canceled.
                </p>
            </div>

            {bannerUrl && (
                <BannerVideo
                    src={bannerUrl.startsWith('http') ? bannerUrl : `https://pastamoalboal.shop${bannerUrl}`}
                    onError={() => setBannerUrl(null)}
                />
            )}

            <h2 className="section-title">Menu</h2>
            <div className="product-list">
                {products.map(item => (
                    <div className="product-item" key={item.id}>
                        <div className="image-container">
                            <img
                                src={item.image_url?.startsWith('http') ? item.image_url : `https://pastamoalboal.shop${item.image_url}`}
                                alt={item.name}
                                className="product-img"
                                loading="lazy"
                                onLoad={(e) => e.target.parentElement.classList.add('loaded')}
                                onError={(e) => {e.target.src = 'https://placehold.co/400x300?text=No+Image'}}
                            />
                        </div>
                        <div className="product-info">
                            <h3>{item.name}</h3>
                            <div className="footer">
                                <span className="price">₱{item.price}</span>
                                {cart.find(x => x.id === item.id) ? (
                                    <div className="counter">
                                        <button className="btn" onClick={() => onRemove(item)}>−</button>
                                        <span>{cart.find(x => x.id === item.id).quantity}</span>
                                        <button className="btn" onClick={() => onAdd(item)}>+</button>
                                    </div>
                                ) : (
                                    <button className="add-btn" onClick={() => onAdd(item)}>ADD</button>
                                )}
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* 👇 Единая кастомная кнопка для всех платформ */}
            {cart.length > 0 && (
                <div className="web-checkout-container">
                    <button className="web-checkout-btn" onClick={onCheckout} disabled={orderStatus === 'sending'}>
                        <span className="checkout-label">
                            <span className="checkout-count">{itemCount}</span>
                            {orderStatus === 'sending' ? 'Sending…' : 'Place order'}
                        </span>
                        <span>₱{getTotalPrice().toLocaleString('en-US')}</span>
                    </button>
                </div>
            )}
            
            <div style={{ height: '100px' }}></div>
        </div>
    );
};

export default App;
