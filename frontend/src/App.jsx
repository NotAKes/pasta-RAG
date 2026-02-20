import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

const tg = window.Telegram.WebApp;

const App = () => {
    const [products, setProducts] = useState([]);
    const [cart, setCart] = useState([]);
    const [loading, setLoading] = useState(true);
    const [orderStatus, setOrderStatus] = useState(null);

    // Состояния для ввода данных
    const [name, setName] = useState('');
    const [phone, setPhone] = useState('');

    // 👇 Твой токен (Вставлен жестко, как ты просил)
    const SECRET_TOKEN = "1yQ!={shr[RX3tj12w34554w2Ejyj6wef1WZ)<XtV>";

    // 1. Загрузка меню
    useEffect(() => {
        tg.ready();
        tg.expand();

        const fetchProducts = async () => {
            try {
                // Проверь адрес: /api или /api/products (зависит от твоего api.py)
                // Обычно мы делали /api/products
                const response = await fetch('https://pastamoalboal.shop/api/', {
                    headers: { 'Content-Type': 'application/json' }
                });

                if (!response.ok) throw new Error('Failed to fetch menu');

                const data = await response.json();
                setProducts(data);
            } catch (error) {
                console.error("Error:", error);
                tg.showAlert("Error loading menu");
            } finally {
                setLoading(false);
            }
        };

        fetchProducts();

        // Автозаполнение имени из Телеграма
        if (tg.initDataUnsafe?.user?.first_name) {
            setName(tg.initDataUnsafe.user.first_name);
        }
    }, []);

    // 2. Логика корзины (Добавление/Удаление)
    const onAdd = (product) => {
        const exist = cart.find(x => x.id === product.id);
        if (exist) {
            setCart(cart.map(x => x.id === product.id ? { ...exist, quantity: exist.quantity + 1 } : x));
        } else {
            setCart([...cart, { ...product, quantity: 1 }]);
        }
        if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
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

    // 3. ОТПРАВКА ЗАКАЗА (ИСПРАВЛЕНО ПОД СКРИНШОТ МОДЕЛИ)
    const onCheckout = useCallback(async () => {
        if (cart.length === 0) return;

        // Валидация: если нет профиля ТГ и поля пустые
        if (!tg.initDataUnsafe?.user && (!name || !phone)) {
            tg.showAlert("Please enter your Name and Phone!");
            return;
        }

        setOrderStatus('sending');

        // 👇 СОБИРАЕМ ДАННЫЕ СТРОГО ПО МОДЕЛИ ИЗ СКРИНШОТА
        const data = {
            // Модель OrderRequest
            user_id: tg.initDataUnsafe?.user?.id || null, // Optional[int]
            name: name,                                    // Optional[str]
            phone: phone,                                  // Optional[str]
            table: "1",                                    // str (Обязательное!)

            // Модель OrderItem (в списке items)
            items: cart.map(item => ({
                id: String(item.id), // Python ждет str
                title: item.name,    // ВАЖНО: Python ждет 'title', а не 'name'!
                price: item.price,   // float
                quantity: item.quantity // int
            }))
        };

        try {
            const response = await fetch('https://pastamoalboal.shop/api/create_order', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Secret-Token': SECRET_TOKEN
                },
                body: JSON.stringify(data),
            });

            if (response.ok) {
                setOrderStatus('success');
                tg.MainButton.hide();
                setTimeout(() => tg.close(), 2000);
            } else {
                const errorData = await response.json();
                console.error("Server Error:", errorData);
                throw new Error('Server returned error');
            }
        } catch (error) {
            console.error("Fetch error:", error);
            setOrderStatus('error');
            tg.showAlert("Connection Error. Try again.");
        }
    }, [cart, name, phone]);

    // 4. Кнопка Telegram
    useEffect(() => {
        if (cart.length === 0) {
            tg.MainButton.hide();
        } else {
            tg.MainButton.setParams({
                text: `PAY $${getTotalPrice()}`,
                color: '#2cab37'
            });
            tg.MainButton.show();
        }
        tg.MainButton.onClick(onCheckout);
        return () => tg.MainButton.offClick(onCheckout);
    }, [cart, onCheckout]);

    // 5. Рендеринг
    if (loading) return <div className="loading">Loading...</div>;
    if (orderStatus === 'success') return <div className="success-screen"><h1>Order Sent! ✅</h1></div>;

    return (
        <div className="App">
            <h1 className="title">PastaBar AI 🍝</h1>

            <div className="product-list">
                {products.length === 0 ? <div className="empty">No items</div> : products.map(item => (
                    <div className="product-item" key={item.id}>
                        <div className="image-container">
                             {/* Исправлена обработка картинок */}
                             <img
                                src={item.image_url?.startsWith('http') ? item.image_url : `https://pastamoalboal.shop${item.image_url}`}
                                alt={item.name}
                                className="product-img"
                                onError={(e) => {e.target.src = 'https://placehold.co/400x300?text=No+Image'}}
                            />
                        </div>
                        <div className="product-info">
                            <h3>{item.name}</h3>
                            <p className="desc">{item.description}</p>
                            <div className="footer">
                                <span className="price">${item.price}</span>
                                {cart.find(x => x.id === item.id) ? (
                                    <div className="counter">
                                        <button className="btn" onClick={() => onRemove(item)}>-</button>
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

            {/* Форма ввода (показываем, если есть товары в корзине) */}
            {cart.length > 0 && (
                <div className="form-container" style={{ margin: '20px', padding: '15px', background: '#f5f5f5', borderRadius: '12px' }}>
                    <h3 style={{marginTop: 0}}>Contacts</h3>
                    <input
                        type="text"
                        placeholder="Your Name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className="input-field"
                        style={{ width: '100%', padding: '10px', marginBottom: '10px', borderRadius: '8px', border: '1px solid #ccc', boxSizing: 'border-box' }}
                    />
                    <input
                        type="tel"
                        placeholder="Phone Number"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        className="input-field"
                        style={{ width: '100%', padding: '10px', marginBottom: '5px', borderRadius: '8px', border: '1px solid #ccc', boxSizing: 'border-box' }}
                    />
                </div>
            )}

            <div style={{ height: '100px' }}></div>
        </div>
    );
};

export default App;