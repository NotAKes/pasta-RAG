import { useEffect } from 'react';
import BannerVideo from './components/BannerVideo.jsx';
import CheckoutBar from './components/CheckoutBar.jsx';
import CustomerDetails from './components/CustomerDetails.jsx';
import Hero from './components/Hero.jsx';
import Menu from './components/Menu.jsx';
import { useCart } from './hooks/useCart.js';
import { useCheckout } from './hooks/useCheckout.js';
import { useMenu } from './hooks/useMenu.js';
import { telegram } from './services/telegram.js';
import './App.css';

export default function App() {
  const menu = useMenu();
  const cart = useCart();
  const order = useCheckout(cart.cart);
  useEffect(() => telegram.initialize(), []);

  if (menu.loading) return <main className="loading" role="status"><img src="/logo.png" alt="Pasta Bar" className="logo" />Loading menu…</main>;
  if (menu.error) return (
    <main className="loading">
      <img src="/logo.png" alt="Pasta Bar" className="logo" />
      <h1>Menu unavailable</h1>
      <p role="alert">{menu.error}</p>
      <button type="button" className="add-btn" onClick={menu.retry}>Retry loading menu</button>
    </main>
  );
  if (order.status === 'success') return (
    <main className="success-screen" role="status">
      <img src="/logo.png" alt="Pasta Bar" className="logo" />
      <h1>Order sent!</h1>
      <p>Order for {order.details.table} has been saved.</p>
      {order.notificationStatus === 'sent'
        ? <p>The restaurant has been notified. We'll contact you shortly.</p>
        : <p>Restaurant notification is pending. This is not a confirmed delivery or reservation.</p>}
      <p>Order reference: {order.orderId}</p>
    </main>
  );
  return (
    <main className="App">
      <Hero />
      <form onSubmit={order.checkout} aria-busy={order.status === 'sending'}>
        <CustomerDetails details={order.details} onChange={order.setDetails} disabled={order.status === 'sending'} />
        {menu.bannerUrl && <BannerVideo src={menu.bannerUrl} onError={menu.hideBanner} />}
        {order.error && <p className="error-message" role="alert">{order.error} Your cart has been kept. You can retry below.</p>}
        <Menu products={menu.products} cart={cart.cart} add={cart.add} remove={cart.remove} disabled={order.status === 'sending'} />
        <CheckoutBar itemCount={cart.itemCount} total={cart.total} status={order.status} />
      </form>
    </main>
  );
}
