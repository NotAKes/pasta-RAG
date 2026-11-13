export default function CustomerDetails({ details, onChange, disabled }) {
  const update = (field) => (event) => onChange((details) => ({ ...details, [field]: event.target.value }));
  return (
    <section className="form-container top-form" aria-labelledby="details-heading">
      <h2 className="section-title" id="details-heading">Your details</h2>
      <fieldset disabled={disabled} className="details-fields">
        <div className="form-row">
          <label className="hotel-field">Hotel / table *
            <input id="table" name="table" type="text" placeholder="Hotel" value={details.table} onChange={update('table')} className="input-field" required maxLength={200} />
          </label>
          <label className="name-field">Name
            <input id="name" name="name" type="text" autoComplete="name" placeholder="Name" value={details.name} onChange={update('name')} className="input-field" maxLength={200} />
          </label>
        </div>
        <label htmlFor="contact">Contact *</label>
        <input id="contact" name="phone" type="text" autoComplete="tel" placeholder="Phone, Telegram, WhatsApp…" value={details.phone} onChange={update('phone')} className={`input-field ${!details.phone.trim() ? 'input-required' : ''}`} required maxLength={200} aria-describedby="contact-warning" />
        <p className="contact-warning" id="contact-warning">⚠️ Contact is required. If we can't reach you, your order will be canceled.</p>
      </fieldset>
    </section>
  );
}
