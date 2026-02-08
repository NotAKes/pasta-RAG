import { useState, useEffect, useCallback } from 'react';
import './App.css';

function App() {
  const [menu, setMenu] = useState([]);
  const [cart, setCart] = useState([]);
  const [tableNumber, setTableNumber] = useState('');
  const [isTableLocked, setIsTableLocked] = useState(false);
  const [customerInfo, setCustomerInfo] = useState({ name: '', phone: '' });
  const [errors, setErrors] = useState({ table: false, name: false, phone: false });
  const [isLoading, setIsLoading] = useState(true);

  // --- СОСТОЯНИЕ ЮЗЕРА ---
  const [tgUser, setTgUser] = useState(null);

  // 1. Умная загрузка Телеграма (Решение проблемы "Не обнаружен")
  useEffect(() => {
    let intervalId;
    let attempts = 0;

    const checkTelegram = () => {
        attempts++;
        const tg = window.Telegram?.WebApp;
        
        // Проверяем: скрипт загрузился? данные есть?
        if (tg && tg.initDataUnsafe?.user?.id) {
            console.log("Telegram User Found:", tg.initDataUnsafe.user);
            
            setTgUser(tg.initDataUnsafe.user); // Сохраняем юзера
            
            // Настройка внешнего вида
            tg.ready();
            tg.expand();
            if (tg.themeParams?.bg_color) {
                document.body.style.backgroundColor = tg.themeParams.bg_color;
                document.body.style.color = tg.themeParams.text_color;
            }
            
            clearInterval(intervalId); // Всё нашли, останавливаем таймер
        } else if (attempts > 20) {
            // Если через 2 секунды (20 * 100мс) ничего нет - сдаемся
            clearInterval(intervalId);
        }
    };

    // Запускаем проверку каждые 100мс
    intervalId = setInterval(checkTelegram, 100);
    
    // Пробуем проверить сразу
    checkTelegram();

    return () => clearInterval(intervalId);
  }, []);

  // Вспомогательная переменная для удобства
  const hasAuth = !!tgUser?.id;

  // --- ЗАГРУЗКА МЕНЮ ---
  useEffect(() => {
    fetch('/api')
      .then(res => res.json())
      .then(data => {
        const items = Array.isArray(data) ? data : [data];
        setMenu(items.filter(item => item.metadata?.price > 0));
      })
      .catch(e => console.error(e))
      .finally(() => setIsLoading(false));
  }, []);

  // --- ССЫЛКИ И QR ---
  useEffect(() => {
    if (menu.length === 0) return;
    const tg = window.Telegram?.WebApp; // Тут можно брать напрямую, т.к. меню грузится не мгновенно
    const tgParams = tg?.initDataUnsafe?.start_param;
    const urlParams = new URLSearchParams(window.location.search);
    
    let foundTable = urlParams.get('table');
    if (tgParams && tgParams.startsWith('table_')) foundTable = tgParams.replace('table_', '');
    
    if (foundTable) {
      setTableNumber(foundTable);
      setIsTableLocked(true);
    }
    
    // Deep Linking
    const startOrder = urlParams.get('start_order');
    if (startOrder) {
        const dishNames = startOrder.split(',');
        const recommendedItems = [];
        dishNames.forEach(name => {
            const found = menu.find(m => m.metadata.dish_name === name);
            if (found) recommendedItems.push({ id: found.metadata.dish_name, title: found.metadata.dish_name, price: found.metadata.price, quantity: 1 });
        });
        if (recommendedItems.length > 0) setCart(recommendedItems);
    }
  }, [menu]);

  // --- КОРЗИНА ---
  const onAdd = (item) => {
    const existing = cart.find(c => c.id === item.metadata.dish_name);
    if (existing) setCart(cart.map(c => c.id === existing.id ? { ...c, quantity: c.quantity + 1 } : c));
    else setCart([...cart, { id: item.metadata.dish_name, title: item.metadata.dish_name, price: item.metadata.price, quantity: 1 }]);
    window.Telegram?.WebApp?.HapticFeedback.impactOccurred('light');
  };

  const onRemove = (item) => {
    const existing = cart.find(c => c.id === item.metadata.dish_name);
    if (existing.quantity === 1) setCart(cart.filter(c => c.id !== existing.id));
    else setCart(cart.map(c => c.id === existing.id ? { ...c, quantity: c.quantity - 1 } : c));
    window.Telegram?.WebApp?.HapticFeedback.impactOccurred('light');
  };

  const getTotalPrice = () => cart.reduce((acc, item) => acc + (item.price * item.quantity), 0);
  const getQuantity = (item) => cart.find(c => c.id === item.metadata.dish_name)?.quantity || 0;

  // --- ОТПРАВКА ---
  const onSendData = useCallback(() => {
    // Сброс ошибок
    let newErrors = { table: false, name: false, phone: false };
    let hasError = false;

    if (!tableNumber) { newErrors.table = true; hasError = true; }

    // Если ID нет, требуем форму
    if (!hasAuth) {
        if (!customerInfo.name) { newErrors.name = true; hasError = true; }
        if (!customerInfo.phone) { newErrors.phone = true; hasError = true; }
    }

    if (hasError) {
        setErrors(newErrors);
        window.Telegram?.WebApp?.HapticFeedback.notificationOccurred('error');
        if (newErrors.name || newErrors.phone) document.querySelector('.web-form')?.scrollIntoView({ behavior: 'smooth' });
        return;
    }

    const orderData = {
        user_id: tgUser?.id || null, // Берем из стейта
        name: !hasAuth ? customerInfo.name : (tgUser.first_name || "Guest"),
        phone: !hasAuth ? customerInfo.phone : "Telegram",
        table: tableNumber,
        items: cart
    };

    fetch('/api/create_order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orderData)
    }).then(res => {
        if (res.ok) {
            window.Telegram?.WebApp?.close();
            // Fallback для браузера
            if (!tgUser) {
                alert("✅ Заказ принят!");
                setCart([]);
                setCustomerInfo({name:'', phone:''});
            }
        } else {
            alert("Ошибка сервера");
        }
    });
  }, [cart, tableNumber, customerInfo, hasAuth, tgUser]);

  // --- НАТИВНАЯ КНОПКА ---
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg) return;

    tg.onEvent('mainButtonClicked', onSendData);

    if (cart.length > 0 && hasAuth) {
        tg.MainButton.text = `ЗАКАЗАТЬ: ${getTotalPrice()} PHP`;
        tg.MainButton.show();
        tg.MainButton.enable();
    } else {
        tg.MainButton.hide();
    }
    return () => tg.offEvent('mainButtonClicked', onSendData);
  }, [cart, onSendData, hasAuth]);

  if (isLoading) return <div className="loading">Loading...</div>;

  return (
    <div className="container">
      {/* ОТЛАДКА: Показывает текущий статус */}
      <div style={{ fontSize: '10px', color: '#999', textAlign: 'center', marginBottom: '5px' }}>
        STATUS: {tgUser ? `✅ ID: ${tgUser.id}` : "⏳ Searching..."}
      </div>

      <h1 className="header">Menu 🍔</h1>
      
      <div className={`table-input-container ${errors.table ? 'error-box' : ''}`}>
        <label>Стол №</label>
        <input 
            value={tableNumber} 
            onChange={(e) => { setTableNumber(e.target.value); setErrors(prev => ({...prev, table: false})) }} 
            disabled={isTableLocked} 
            className={isTableLocked ? "locked-input" : ""} 
            placeholder="—"
        />
      </div>

      {/* Показываем форму, если мы НЕ нашли юзера */}
      {cart.length > 0 && !tgUser && (
        <div className="web-form">
            <h3>Ваши контакты:</h3>
            <p className="hint">
               {errors.name || errors.phone ? <span style={{color: 'red'}}>Заполните поля!</span> : "Телеграм не передал профиль. Введите данные:"}
            </p>
            <input placeholder="Имя" value={customerInfo.name} className={errors.name ? 'input-error' : ''} onChange={e => { setCustomerInfo({...customerInfo, name: e.target.value}); setErrors(prev => ({...prev, name: false})) }} />
            <input placeholder="Телефон" value={customerInfo.phone} className={errors.phone ? 'input-error' : ''} onChange={e => { setCustomerInfo({...customerInfo, phone: e.target.value}); setErrors(prev => ({...prev, phone: false})) }} />
            
            <button className="web-main-button" onClick={onSendData} style={{marginTop: '10px'}}>
                ✅ ОТПРАВИТЬ ЗАКАЗ ({getTotalPrice()} PHP)
            </button>
        </div>
      )}

      {/* Меню */}
      <div className="menu-grid">
        {menu.map((item, index) => (
            <div key={index} className="card">
              <div className="image-container">
                {item.metadata.image_url ? <img src={item.metadata.image_url} /> : <div className="placeholder">🍝</div>}
              </div>
              <div className="card-content">
                <h3>{item.metadata.dish_name}</h3>
                <div className="price-row">
                  <span className="price">{item.metadata.price} PHP</span>
                  {getQuantity(item) === 0 ? <button className="add-btn" onClick={() => onAdd(item)}>ADD</button> : 
                    <div className="counter-btn"><button onClick={() => onRemove(item)}>-</button><span>{getQuantity(item)}</span><button onClick={() => onAdd(item)}>+</button></div>}
                </div>
              </div>
            </div>
        ))}
      </div>
      
      {/* Кнопка для обычного браузера (если юзер найден, но кнопка ТГ не работает) */}
      {cart.length > 0 && tgUser && !window.Telegram?.WebApp?.initData && (
          <button className="web-main-button" onClick={onSendData}>ЗАКАЗАТЬ</button>
      )}
      
      <div style={{height: 100}}></div>
    </div>
  );
}

export default App;