import { useState } from 'react';
import { MAX_QUANTITY } from '../lib/menu.js';
import { mediaUrl } from '../services/api.js';

function ProductImage({ item }) {
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const src = mediaUrl(item.image_url);
  return (
    <div className={`image-container ${loaded || failed || !src ? 'loaded' : ''}`}>
      {src && !failed ? <img src={src} alt={item.name} className="product-img" loading="lazy" onLoad={() => setLoaded(true)} onError={() => setFailed(true)} /> : <div className="image-placeholder" aria-label={`No image for ${item.name}`}>🍝</div>}
    </div>
  );
}

export default function Menu({ products, cart, add, remove, disabled }) {
  const quantities = new Map(cart.map((item) => [item.id, item.quantity]));
  return (
    <section aria-labelledby="menu-heading">
      <h2 className="section-title" id="menu-heading">Menu</h2>
      {!products.length && <p role="status">The menu is currently empty. Please check back shortly.</p>}
      <div className="product-list">
        {products.map((item) => {
          const quantity = quantities.get(item.id) || 0;
          return (
            <article className="product-item" key={item.id}>
              <ProductImage item={item} />
              <div className="product-info">
                <h3>{item.name}</h3>
                <div className="footer">
                  <span className="price">₱{item.price.toLocaleString('en-US')}</span>
                  {quantity ? <div className="counter">
                    <button type="button" className="btn" onClick={() => remove(item)} disabled={disabled} aria-label={`Remove one ${item.name}`}>−</button>
                    <span aria-live="polite" aria-label={`${quantity} ${item.name} in cart`}>{quantity}</span>
                    <button type="button" className="btn" onClick={() => add(item)} disabled={disabled || quantity >= MAX_QUANTITY} aria-label={`Add one ${item.name}`} title={quantity >= MAX_QUANTITY ? 'Maximum 20 per dish' : undefined}>+</button>
                  </div> : <button type="button" className="add-btn" onClick={() => add(item)} disabled={disabled} aria-label={`Add ${item.name}`}>ADD</button>}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
