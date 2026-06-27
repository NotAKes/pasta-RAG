import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

const tg = window.Telegram.WebApp;

const App = () => {
    const [products, setProducts] = useState([]);
    const [cart, setCart] = useState([]);
    const [loading, setLoading] = useState(true);
    const [orderStatus, setOrderStatus] = useState(null);

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
    if (loading) return <div className="loading">Loading Menu...</div>;
    if (orderStatus === 'success') return <div className="success-screen"><h1>✅ Order Sent!</h1><p>ROOM №{table}</p></div>;

    return (
        <div className="App">
            <h1 className="title">Pastabar AI 🍝</h1>

            {/* Блок контактов и выбора стола */}
            <div className="form-container top-form">
                <div style={{display: 'flex', gap: '8px'}}>
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

            <div className="product-list">
                {products.map(item => (
                    <div className="product-item" key={item.id}>
                        <div className="image-container">
                            <img
                                src={item.image_url?.startsWith('http') ? item.image_url : `https://pastamoalboal.shop${item.image_url}`}
                                alt={item.name}
                                className="product-img"
                                onError={(e) => {e.target.src = 'https://placehold.co/400x300?text=No+Image'}}
                            />
                        </div>
                        <div className="product-info">
                            <h3>{item.name}</h3>
                            <div className="footer">
                                <span className="price">{item.price} PHP</span>
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

            {/* 👇 Единая кастомная кнопка для всех платформ */}
            {cart.length > 0 && (
                <div className="web-checkout-container">
                    <button className="web-checkout-btn" onClick={onCheckout}>
                        ORDER FOR ROOM {table || '?'} ({getTotalPrice()} PHP)
                    </button>
                </div>
            )}
            
            <div style={{ height: '100px' }}></div>
        </div>
    );
};

export default App;
