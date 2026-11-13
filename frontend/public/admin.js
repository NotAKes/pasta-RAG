window.initializeAdmin = function initializeAdmin({ apiBaseUrl, mediaUrl }) {
    const API = apiBaseUrl;
    let TOKEN = localStorage.getItem('admin_token') || '';
    let items = []; // raw instruction.json items

    function toast(msg, ms = 2200) {
      const t = document.getElementById('toast');
      t.textContent = msg; t.classList.add('show');
      clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('show'), ms);
    }

    async function login() {
      const tk = document.getElementById('token').value.trim();
      if (!tk) return;
      TOKEN = tk;
      const ok = await loadMenu();
      if (ok) {
        localStorage.setItem('admin_token', tk);
      } else {
        document.getElementById('loginError').textContent = 'Invalid token or server error.';
      }
    }

    function logout() {
      localStorage.removeItem('admin_token');
      TOKEN = '';
      document.getElementById('panel').classList.add('hidden');
      document.getElementById('login').classList.remove('hidden');
    }

    async function loadMenu() {
      try {
        const r = await fetch(API + '/api/admin/menu', { headers: { 'X-Admin-Token': TOKEN } });
        if (!r.ok) return false;
        items = await r.json();
        document.getElementById('login').classList.add('hidden');
        document.getElementById('panel').classList.remove('hidden');
        render();
        loadBanner();
        return true;
      } catch {
        return false;
      }
    }

    function metaVal(it, key, def = '') {
      return (it.metadata && it.metadata[key] != null) ? it.metadata[key] : def;
    }

    // Technical "info" blocks feed the AI bot's knowledge base — they are not
    // dishes. We hide them from the admin UI but keep them in `items` so they
    // are preserved untouched when the menu is saved.
    function isInfoItem(it) {
      return !!(it.metadata && Array.isArray(it.metadata.categories) && it.metadata.categories.includes('info'));
    }

    function render() {
      const list = document.getElementById('list');
      list.innerHTML = '';

      const dishCount = items.filter(it => !isInfoItem(it)).length;
      let shown = 0;
      items.forEach((it, idx) => {
        if (isInfoItem(it)) return; // skip technical info blocks
        shown++;
        const card = document.createElement('div');
        card.className = 'card';
        card.dataset.idx = idx;
        const img = metaVal(it, 'image_url');
        const imgSrc = mediaUrl(img) || '/logo.png';
        const cats = (it.metadata && Array.isArray(it.metadata.categories)) ? it.metadata.categories.join(', ') : '';

        card.innerHTML = `
          <div class="thumb-col">
            <img class="thumb" src="${escAttr(imgSrc)}" alt="Dish preview" onerror="this.onerror=null;this.src='/logo.png'"/>
            <button class="btn secondary" style="font-size:12px;padding:6px 10px" onclick="pickImage(${idx})">Upload</button>
          </div>
          <div>
            <div class="row">
              <div>
                <label for="dish_name-${idx}">Dish name</label>
                <input id="dish_name-${idx}" value="${escAttr(metaVal(it, 'dish_name'))}" oninput="setMeta(${idx},'dish_name',this.value)"/>
              </div>
              <div style="max-width:120px">
                <label for="price-${idx}">Price (PHP)</label>
                <input id="price-${idx}" type="number" min="0" step="0.01" value="${escAttr(metaVal(it, 'price', 0))}" oninput="setMeta(${idx},'price',Number(this.value))"/>
              </div>
            </div>
            <label for="image_url-${idx}">Image URL</label>
            <input id="image_url-${idx}" value="${escAttr(metaVal(it, 'image_url'))}" oninput="setMeta(${idx},'image_url',this.value); refreshThumb(${idx},this.value)"/>
            <label for="categories-${idx}">Categories (comma separated)</label>
            <input id="categories-${idx}" value="${escAttr(cats)}" oninput="setCategories(${idx}, this.value)"/>
            <label for="text-${idx}">Text / description</label>
            <textarea id="text-${idx}" rows="3" oninput="setText(${idx}, this.value)">${escHtml(it.text || '')}</textarea>
          </div>
          <div class="card-actions">
            <div style="display:flex;align-items:center;gap:8px">
              <span class="badge">#</span>
              <input class="pos-input" type="number" min="1" max="${dishCount}" value="${shown}"
                onchange="moveDishTo(${idx}, Number(this.value))"
                onkeydown="if(event.key==='Enter'){this.blur();}"
                onfocus="this.select()"
                title="Type a position and press Enter to move this dish there"/>
              <button class="btn secondary move-btn" ${shown === 1 ? 'disabled' : ''} onclick="moveDish(${idx},-1)" title="Move up">↑</button>
              <button class="btn secondary move-btn" ${shown === dishCount ? 'disabled' : ''} onclick="moveDish(${idx},1)" title="Move down">↓</button>
            </div>
            <button class="btn danger" onclick="removeDish(${idx})">Delete</button>
          </div>
        `;
        list.appendChild(card);
      });

      document.getElementById('count').textContent = shown + ' dishes';
    }

    function escAttr(s) { return escHtml(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
    function escHtml(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

    function ensureMeta(idx) { if (!items[idx].metadata) items[idx].metadata = {}; return items[idx].metadata; }
    function setMeta(idx, key, val) { ensureMeta(idx)[key] = val; }
    function setText(idx, val) { items[idx].text = val; }
    function setCategories(idx, val) {
      ensureMeta(idx).categories = val.split(',').map(s => s.trim()).filter(Boolean);
    }
    function refreshThumb(idx, val) {
      const card = document.querySelector('.card[data-idx="' + idx + '"]');
      if (card) card.querySelector('.thumb').src = mediaUrl(val) || '/logo.png';
    }

    function addDish() {
      items.push({
        text: 'Dish: New Dish. Description: ...',
        metadata: { categories: ['menu'], dish_name: 'New Dish', price: 0, image_url: '' }
      });
      render();
      window.scrollTo(0, document.body.scrollHeight);
    }

    function removeDish(idx) {
      if (!confirm('Delete "' + metaVal(items[idx], 'dish_name', 'this item') + '"?')) return;
      items.splice(idx, 1);
      render();
    }

    // Move a dish up (dir=-1) or down (dir=+1) by swapping it with the nearest
    // neighbouring dish, skipping hidden info blocks. This reorders how dishes
    // appear in the menu.
    function moveDish(idx, dir) {
      let t = idx + dir;
      while (t >= 0 && t < items.length && isInfoItem(items[t])) t += dir;
      if (t < 0 || t >= items.length) return; // no dish neighbour in that direction
      [items[idx], items[t]] = [items[t], items[idx]];
      render();
    }

    // Quick move: place the dish at absolute index `idx` at 1-based dish
    // position `targetPos`. Everything at/after that position shifts one down.
    // Hidden info blocks keep their absolute slots; only dishes are permuted.
    function moveDishTo(idx, targetPos) {
      const dishIdxs = items.map((_, i) => i).filter(i => !isInfoItem(items[i]));
      const total = dishIdxs.length;
      if (!Number.isFinite(targetPos)) return render(); // reset a bad input
      targetPos = Math.max(1, Math.min(total, Math.round(targetPos)));
      const curPos = dishIdxs.indexOf(idx) + 1;
      if (!curPos || curPos === targetPos) return render();

      const dishes = dishIdxs.map(i => items[i]);
      const [moved] = dishes.splice(curPos - 1, 1);
      dishes.splice(targetPos - 1, 0, moved);
      dishIdxs.forEach((absIdx, k) => { items[absIdx] = dishes[k]; });
      render();
    }

    function pickImage(idx) {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*';
      input.onchange = () => {
        const file = input.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async () => {
          toast('Uploading image...');
          try {
            const r = await fetch(API + '/api/admin/upload', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-Admin-Token': TOKEN },
              body: JSON.stringify({ data: reader.result })
            });
            if (!r.ok) throw new Error('upload failed');
            const j = await r.json();
            setMeta(idx, 'image_url', j.url);
            render();
            toast('Image uploaded ✓');
          } catch {
            toast('Upload failed ✗');
          }
        };
        reader.readAsDataURL(file);
      };
      input.click();
    }

    function showBanner(url) {
      const v = document.getElementById('bannerPreview');
      document.getElementById('bannerEmpty').classList.toggle('hidden', !!url);
      document.getElementById('bannerDeleteBtn').classList.toggle('hidden', !url);
      v.classList.toggle('hidden', !url);
      if (url) { v.src = mediaUrl(url); } else { v.removeAttribute('src'); v.load(); }
    }

    async function loadBanner() {
      try {
        const r = await fetch(API + '/api/banner');
        showBanner(r.ok ? (await r.json()).video_url : null);
      } catch { showBanner(null); }
    }

    function pickBanner() {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'video/mp4,video/webm,video/quicktime';
      input.onchange = () => {
        const file = input.files[0];
        if (!file) return;
        if (file.size > 100 * 1024 * 1024) { toast('Video too large (max 100MB) ✗', 3500); return; }
        const btn = document.getElementById('bannerUploadBtn');
        btn.disabled = true;
        const xhr = new XMLHttpRequest();
        xhr.open('POST', API + '/api/admin/banner');
        xhr.setRequestHeader('X-Admin-Token', TOKEN);
        xhr.setRequestHeader('Content-Type', file.type || 'video/mp4');
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) btn.textContent = 'Uploading ' + Math.round(e.loaded / e.total * 100) + '%';
        };
        xhr.onloadend = () => {
          btn.disabled = false; btn.textContent = 'Upload video';
          if (xhr.status === 200) {
            showBanner(JSON.parse(xhr.responseText).video_url);
            toast('Banner video uploaded ✓');
          } else {
            let msg = 'Upload failed ✗';
            try { msg = JSON.parse(xhr.responseText).detail + ' ✗'; } catch { /* Keep the generic upload error. */ }
            toast(msg, 3500);
          }
        };
        xhr.send(file);
      };
      input.click();
    }

    async function deleteBanner() {
      if (!confirm('Remove the banner video from the site?')) return;
      try {
        const r = await fetch(API + '/api/admin/banner', { method: 'DELETE', headers: { 'X-Admin-Token': TOKEN } });
        if (!r.ok) throw new Error();
        showBanner(null);
        toast('Banner removed ✓');
      } catch { toast('Remove failed ✗'); }
    }

    async function saveAll() {
      const btn = document.getElementById('saveBtn');
      btn.disabled = true; btn.textContent = 'Saving...';
      try {
        const r = await fetch(API + '/api/admin/menu', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Admin-Token': TOKEN },
          body: JSON.stringify(items)
        });
        if (!r.ok) throw new Error('save failed');
        const j = await r.json();
        toast('Saved ' + j.count + ' items ✓');
      } catch {
        toast('Save failed ✗');
      } finally {
        btn.disabled = false; btn.textContent = '💾 Save all';
      }
    }

    // Existing inline handlers remain available after moving this script into a module.
    Object.assign(window, {
      login, logout, addDish, saveAll, pickBanner, deleteBanner, pickImage,
      setMeta, setText, setCategories, refreshThumb, moveDish, moveDishTo, removeDish,
    });
    document.getElementById('token').addEventListener('keydown', (event) => {
      if (event.key === 'Enter') login();
    });

    // Auto-login if token stored
    if (TOKEN) {
      document.getElementById('token').value = TOKEN;
      loadMenu().then((ok) => {
        if (!ok) document.getElementById('loginError').textContent = 'Session unavailable. Sign in to retry.';
      });
    }
}
