export default function CheckoutBar({ itemCount, total, status }) {
  if (!itemCount) return null;
  return (
    <div className="web-checkout-container">
      <button type="submit" className="web-checkout-btn" disabled={status === 'sending'}>
        <span className="checkout-label">
          <span className="checkout-count">{itemCount}</span>
          {status === 'sending' ? 'Sending…' : status === 'error' ? 'Retry order' : 'Place order'}
        </span>
        <span>₱{total.toLocaleString('en-US')}</span>
      </button>
    </div>
  );
}
