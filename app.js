// app.js

const VERSION = '2.5.0';

const S = {
  view: 'desk',      // desk | viewer | compare
  artworks: [],
  current: -1,
  compareLeftIdx: -1,
  compareRightIdx: -1,
  annotations: {},
  annoMode: false,
  cropMode: false,
  pickMode: false,
  searchOpen: false,
  helpOpen: false,
  uploadOpen: false,
  key: null,
  salt: null,
  osd: null,
  osd1: null,
  osd2: null,
  pendingAnnotation: false,
  pendingPinCoords: null,
  draggedThisFrame: false,
  cropBlob: null,
};

const OSD_DEFAULTS = {
  prefixUrl: 'https://openseadragon.github.io/openseadragon/images/',
  showNavigationControl: false,
  animationTime: 0.4,
  blendTime: 0.1,
  constrainDuringPan: true,
  maxZoomPixelRatio: 10,
  minZoomLevel: 0.5,
  visibilityRatio: 1,
  zoomPerScroll: 1.2,
  timeout: 120000,
  immediateRender: false,
  imageLoaderLimit: 4,
  maxImageCacheCount: 64,
  tileRetryMax: 0,
  tileRetryDelay: 0,
  subPixelRoundingForTransparency: false,
  gestureSettingsMouse: { scrollToZoom: false, clickToZoom: false, dblClickToZoom: true, pinchToZoom: true },
  gestureSettingsTouch: { scrollToZoom: false, clickToZoom: false, dblClickToZoom: true, pinchToZoom: true, flickEnabled: true },
  gestureSettingsPen:   { scrollToZoom: false, clickToZoom: true,  dblClickToZoom: true },
  flickEnabled: true,
  flickMomentum: 0.4,
};


async function deriveKey(passphrase, salt) {
  const enc = new TextEncoder();
  const mat = await crypto.subtle.importKey('raw', enc.encode(passphrase), 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: 100000, hash: 'SHA-256' },
    mat, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']
  );
}

async function encryptText(text, key) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const data = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, new TextEncoder().encode(text));
  return { iv: Array.from(iv), data: Array.from(new Uint8Array(data)) };
}

async function decryptText(enc, key) {
  const iv   = new Uint8Array(enc.iv);
  const data = new Uint8Array(enc.data);
  const out  = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, data);
  return new TextDecoder().decode(out);
}


function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function api(path, opts) {
  return fetch(path, opts).then(r => {
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
  });
}

let toastTimer = null;
function showToast(msg, isError = false) {
  const t = document.getElementById(isError ? 'toastError' : 'toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3000);
}

function showConfirm(msg, okLabel = 'Remove') {
  return new Promise(resolve => {
    document.getElementById('confirmMsg').textContent = msg;
    const okBtn     = document.querySelector('.btn-confirm-ok');
    const cancelBtn = document.querySelector('.btn-confirm-cancel');
    okBtn.textContent = okLabel;
    document.getElementById('confirmOverlay').classList.add('active');

    function done(result) {
      document.getElementById('confirmOverlay').classList.remove('active');
      okBtn.removeEventListener('click', onOk);
      cancelBtn.removeEventListener('click', onCancel);
      resolve(result);
    }
    const onOk     = () => done(true);
    const onCancel = () => done(false);
    okBtn.addEventListener('click', onOk);
    cancelBtn.addEventListener('click', onCancel);
  });
}


function initGradient() {
  if (typeof THREE === 'undefined') return setTimeout(initGradient, 100);

  const container = document.getElementById('gradientCanvas');
  const renderer  = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'low-power' });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(0.5);
  container.appendChild(renderer.domElement);

  const scene  = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0e1a);
  const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 10000);
  camera.position.z = 50;

  const clock    = new THREE.Clock();
  const uniforms = {
    uTime: { value: 0 },
    uRes:  { value: new THREE.Vector2(window.innerWidth, window.innerHeight) },
    uC1:   { value: new THREE.Vector3(0.03, 0.06, 0.10) },
    uC2:   { value: new THREE.Vector3(0.02, 0.04, 0.07) },
    uC3:   { value: new THREE.Vector3(0.04, 0.08, 0.12) },
  };

  const mat = new THREE.ShaderMaterial({
    uniforms,
    vertexShader: `varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
    fragmentShader: `
      uniform float uTime; uniform vec2 uRes;
      uniform vec3 uC1, uC2, uC3; varying vec2 vUv;
      void main(){
        vec2 uv=vUv;
        vec2 c1=vec2(0.5+sin(uTime*0.25)*0.3,0.5+cos(uTime*0.3)*0.3);
        vec2 c2=vec2(0.5+cos(uTime*0.35)*0.4,0.5+sin(uTime*0.28)*0.4);
        vec2 c3=vec2(0.5+sin(uTime*0.22)*0.35,0.5+cos(uTime*0.38)*0.35);
        float d1=length(uv-c1), d2=length(uv-c2), d3=length(uv-c3);
        float i1=1.0-smoothstep(0.0,0.6,d1), i2=1.0-smoothstep(0.0,0.6,d2), i3=1.0-smoothstep(0.0,0.6,d3);
        vec3 col=vec3(0.02,0.03,0.06);
        col+=uC1*i1*(0.5+0.5*sin(uTime*0.4));
        col+=uC2*i2*(0.5+0.5*cos(uTime*0.5));
        col+=uC3*i3*(0.5+0.5*sin(uTime*0.35));
        col+=sin(uv.x*8.0+uTime*0.2)*cos(uv.y*8.0+uTime*0.3)*0.04;
        gl_FragColor=vec4(col,1.0);
      }`
  });

  scene.add(new THREE.Mesh(new THREE.PlaneGeometry(100, 100), mat));

  let raf = null, lastFrame = 0;
  const FRAME_MS = 1000 / 20;

  function animate(ts) {
    raf = requestAnimationFrame(animate);
    if (ts - lastFrame < FRAME_MS) return;
    lastFrame = ts;
    uniforms.uTime.value += clock.getDelta();
    renderer.render(scene, camera);
  }

  window.gradientPlay = () => {
    if (!raf) { clock.getDelta(); lastFrame = 0; raf = requestAnimationFrame(animate); }
  };
  window.gradientPause = () => {
    if (raf) { cancelAnimationFrame(raf); raf = null; }
  };

  gradientPlay();

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    uniforms.uRes.value.set(window.innerWidth, window.innerHeight);
  });
}


function renderDesk() {
  const grid = document.getElementById('deskGrid');
  grid.innerHTML = '';

  if (S.artworks.length === 0) {
    grid.innerHTML = `
      <div class="empty-desk">
        <h2>Your desk is empty</h2>
        <p>Press <kbd style="font-family:'Space Grotesk',monospace;font-size:12px;background:rgba(60,140,120,0.15);padding:3px 8px;border-radius:5px;color:var(--accent);border:1px solid var(--card-border);">U</kbd> to add your first artwork</p>
      </div>`;
    return;
  }

  S.artworks.forEach((art, i) => {
    const card = document.createElement('div');
    card.className = 'desk-card';
    card.style.transitionDelay = `${Math.min(i * 0.04, 0.3)}s`;
    card.innerHTML = `
      <div class="card-image-wrap">
        <img class="card-image" src="${esc(art.thumbnail)}" alt="${esc(art.name)}" loading="lazy">
        ${art.annotations ? `<div class="card-badge">${art.annotations} note${art.annotations !== 1 ? 's' : ''}</div>` : ''}
        <button class="card-delete" title="Remove artwork">×</button>
      </div>
      <div class="card-meta">
        <div class="card-title">${esc(art.name)}</div>
        <div class="card-slug">${esc(art.slug)}</div>
      </div>
    `;
    card.querySelector('.card-delete').addEventListener('click', e => {
      e.stopPropagation();
      deleteArtwork(i);
    });
    card.addEventListener('click', () => openViewer(i));
    card.addEventListener('mousemove', e => {
      const r = card.getBoundingClientRect();
      card.style.setProperty('--cx', ((e.clientX - r.left) / r.width * 100) + '%');
      card.style.setProperty('--cy', ((e.clientY - r.top) / r.height * 100) + '%');
    });
    grid.appendChild(card);
    requestAnimationFrame(() => card.classList.add('visible'));
  });
}

async function deleteArtwork(index) {
  const art = S.artworks[index];
  if (!await showConfirm(`Remove "${art.name}" from the desk?`)) return;
  if (S.view !== 'desk' && S.current === index) goDesk();
  try {
    const res = await fetch(`/api/artworks/${art.slug}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('delete failed');
    S.artworks = await api('/api/artworks');
    renderDesk();
    showToast('Artwork removed');
  } catch(e) {
    showToast('Failed to remove artwork', true);
  }
}


function openViewer(index) {
  S.current = index;
  S.view    = 'viewer';
  gradientPause();

  const art = S.artworks[index];
  location.hash = '#/artwork/' + art.slug;

  document.getElementById('deskView').style.opacity      = '0';
  document.getElementById('deskView').style.pointerEvents = 'none';
  document.getElementById('viewerView').classList.add('active');
  document.getElementById('vtName').textContent = art.name;
  document.getElementById('vtSlug').textContent = art.slug;

  setTimeout(() => {
    if (!S.osd) {
      S.osd = OpenSeadragon({ id: 'osdViewer', ...OSD_DEFAULTS });
      S.osd.addHandler('update-viewport', () => {
        if (S.view === 'viewer') repositionPins();
      });
    }
    S.osd.open(art.path);
  }, 100);

  loadAnnotations(art.slug);
  renderFilmstrip();
  updateEdges();
  document.getElementById('wipBadge').style.opacity      = '0';
  document.getElementById('wipBadge').style.pointerEvents = 'none';
}

function goDesk() {
  S.view         = 'desk';
  S.annoMode     = false;
  S.cropMode     = false;
  S.pickMode     = false;
  gradientPlay();

  if (S.osd)  { S.osd.destroy();  S.osd  = null; }
  if (S.osd1) { S.osd1.destroy(); S.osd1 = null; }
  if (S.osd2) { S.osd2.destroy(); S.osd2 = null; }

  document.getElementById('viewerView').classList.remove('active', 'pick-mode');
  document.getElementById('compareView').classList.remove('active');
  document.getElementById('deskView').style.opacity      = '1';
  document.getElementById('deskView').style.pointerEvents = 'auto';
  document.getElementById('annotationLayer').classList.remove('active');
  document.getElementById('annotationLayer').innerHTML   = '';
  document.getElementById('cropOverlay').classList.remove('active');
  document.getElementById('cropMarquee').style.display   = 'none';
  document.getElementById('colourChip').classList.remove('show');

  updateEdges();
  document.getElementById('wipBadge').style.opacity      = '0.7';
  document.getElementById('wipBadge').style.pointerEvents = 'none';

  if (location.hash !== '' && location.hash !== '#/') history.pushState(null, '', '#/');
}

function renderFilmstrip() {
  const strip = document.getElementById('filmstrip');
  strip.innerHTML = '';
  S.artworks.forEach((art, i) => {
    const img = document.createElement('img');
    img.className = 'film-thumb' + (i === S.current ? ' active' : '');
    img.src = esc(art.thumbnail);
    img.alt = esc(art.name);
    img.addEventListener('click', () => openViewer(i));
    strip.appendChild(img);
  });
}

function handleTrackpadWheel(e) {
  if (S.view !== 'viewer' || !S.osd) return;
  e.preventDefault();
  const vp   = S.osd.viewport;
  const rect = document.getElementById('osdViewer').getBoundingClientRect();

  if (e.ctrlKey) {
    const factor = Math.exp(-e.deltaY * 0.015);
    const pt = vp.pointFromPixel(new OpenSeadragon.Point(e.clientX - rect.left, e.clientY - rect.top));
    vp.zoomBy(factor, pt, true);
  } else {
    const scale = 1 / (vp.getZoom(true) * rect.width);
    vp.panBy(new OpenSeadragon.Point(e.deltaX * scale, e.deltaY * scale), true);
  }
  vp.applyConstraints();
}

['osdViewer', 'annotationLayer', 'cropOverlay'].forEach(id => {
  document.getElementById(id).addEventListener('wheel', handleTrackpadWheel, { passive: false });
});


async function loadAnnotations(slug) {
  try {
    S.annotations[slug] = await api(`/api/annotations/${slug}`);
  } catch(e) {
    S.annotations[slug] = { salt: null, annotations: [] };
  }
}

function toggleAnnotations() {
  if (S.view !== 'viewer') return;
  S.annoMode = !S.annoMode;

  const layer = document.getElementById('annotationLayer');
  layer.classList.toggle('active', S.annoMode);
  document.querySelector('.edge-btn[title="Annotations"]').classList.toggle('active', S.annoMode);

  if (S.annoMode) {
    const data = S.annotations[S.artworks[S.current].slug] || { annotations: [] };
    if (data.annotations.length > 0 && !S.key) {
      document.getElementById('passModal').classList.add('active');
      S.pendingAnnotation = true;
    } else {
      renderPins();
    }
  } else {
    layer.innerHTML = '';
    S.pendingAnnotation = false;
  }

  showToast(S.annoMode ? 'Click to place a pin' : 'Annotations hidden');
}

async function renderPins() {
  const layer = document.getElementById('annotationLayer');
  layer.innerHTML = '';
  const data = S.annotations[S.artworks[S.current].slug] || { annotations: [] };

  for (let idx = 0; idx < data.annotations.length; idx++) {
    const ann = data.annotations[idx];
    const pin = document.createElement('div');
    pin.className    = 'ann-pin';
    pin.dataset.imgX = ann.x;
    pin.dataset.imgY = ann.y;
    pin.dataset.index = idx;

    let text = '[locked]';
    if (S.key) {
      try { text = await decryptText(ann, S.key); }
      catch(e) { text = '[unreadable note]'; }
    }

    pin.innerHTML = `
      <div class="ann-tooltip">${esc(text)}</div>
      ${S.key ? '<button class="ann-delete-btn" title="Delete note">×</button>' : ''}
    `;
    if (S.key) {
      pin.querySelector('.ann-delete-btn').addEventListener('click', e => {
        e.stopPropagation();
        deleteAnnotation(idx);
      });
    }
    layer.appendChild(pin);
  }
  repositionPins();
}

let repinRaf = null;
function repositionPins() {
  if (repinRaf) return;
  repinRaf = requestAnimationFrame(() => {
    repinRaf = null;
    if (!S.osd || !S.osd.world.getItemAt(0)) return;
    const img = S.osd.world.getItemAt(0);
    const sz  = img.getContentSize();
    document.querySelectorAll('#annotationLayer .ann-pin').forEach(pin => {
      const pt = img.imageToViewerElementCoordinates(
        new OpenSeadragon.Point(parseFloat(pin.dataset.imgX) * sz.x, parseFloat(pin.dataset.imgY) * sz.y)
      );
      pin.style.left = pt.x + 'px';
      pin.style.top  = pt.y + 'px';
    });
  });
}

let dragPin = null;

document.getElementById('annotationLayer').addEventListener('mousedown', e => {
  if (!S.annoMode || !S.key) return;
  const pin = e.target.closest('.ann-pin');
  if (!pin) return;
  e.stopPropagation();
  dragPin = pin;
});

document.addEventListener('mousemove', e => {
  if (!dragPin || !S.osd) return;
  const rect = document.getElementById('osdViewer').getBoundingClientRect();
  const img  = S.osd.world.getItemAt(0);
  const pt   = img.viewerElementToImageCoordinates(new OpenSeadragon.Point(e.clientX - rect.left, e.clientY - rect.top));
  const size = img.getContentSize();
  dragPin.dataset.imgX = Math.max(0, Math.min(1, pt.x / size.x));
  dragPin.dataset.imgY = Math.max(0, Math.min(1, pt.y / size.y));
  repositionPins();
});

document.addEventListener('mouseup', async () => {
  if (!dragPin || !S.key) return;
  const idx  = parseInt(dragPin.dataset.index, 10);
  const slug = S.artworks[S.current].slug;
  const data = S.annotations[slug];
  if (data?.annotations[idx]) {
    data.annotations[idx].x = parseFloat(dragPin.dataset.imgX);
    data.annotations[idx].y = parseFloat(dragPin.dataset.imgY);
    api(`/api/annotations/${slug}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    }).then(() => showToast('Note moved'));
  }
  dragPin = null;
  S.draggedThisFrame = true;
  setTimeout(() => S.draggedThisFrame = false, 80);
});

document.getElementById('annotationLayer').addEventListener('click', async e => {
  if (!S.annoMode || e.target !== document.getElementById('annotationLayer')) return;
  if (S.draggedThisFrame) return;

  const img  = S.osd.world.getItemAt(0);
  const pt   = img.viewerElementToImageCoordinates(new OpenSeadragon.Point(e.offsetX, e.offsetY));
  const size = img.getContentSize();
  const nx   = pt.x / size.x;
  const ny   = pt.y / size.y;

  if (!S.key) {
    document.getElementById('passModal').classList.add('active');
    S.pendingPinCoords = { x: nx, y: ny };
    return;
  }
  createPinEditor(nx, ny);
});

function createPinEditor(nx, ny) {
  const layer = document.getElementById('annotationLayer');
  layer.querySelector('.ann-editor')?.remove();

  const img = S.osd.world.getItemAt(0);
  const pt  = img.imageToViewerElementCoordinates(
    new OpenSeadragon.Point(nx * img.getContentSize().x, ny * img.getContentSize().y)
  );

  const ed = document.createElement('div');
  ed.className  = 'ann-editor';
  ed.style.left = pt.x + 'px';
  ed.style.top  = pt.y + 'px';
  ed.innerHTML  = `
    <textarea placeholder="Your note..."></textarea>
    <div class="ann-actions">
      <button class="btn-cancel">Cancel</button>
      <button class="btn-save">Save</button>
    </div>
  `;

  ed.querySelector('.btn-cancel').addEventListener('click', () => ed.remove());
  ed.querySelector('.btn-save').addEventListener('click', async () => {
    const text = ed.querySelector('textarea').value.trim();
    if (!text) return;
    const slug = S.artworks[S.current].slug;
    const enc  = await encryptText(text, S.key);
    if (!S.annotations[slug]) S.annotations[slug] = { salt: S.salt, annotations: [] };
    S.annotations[slug].annotations.push({ x: nx, y: ny, ...enc });
    api(`/api/annotations/${slug}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(S.annotations[slug])
    }).then(() => showToast('Note saved'));
    ed.remove();
    renderPins();
  });

  layer.appendChild(ed);
  ed.querySelector('textarea').focus();
}

async function deleteAnnotation(index) {
  if (!await showConfirm('Delete this note?', 'Delete')) return;
  const slug = S.artworks[S.current].slug;
  const data = S.annotations[slug];
  if (!data?.annotations[index]) return;
  data.annotations.splice(index, 1);
  if (data.annotations.length === 0) {
    data.salt = null;
    S.key  = null;
    S.salt = null;
  }
  await api(`/api/annotations/${slug}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  renderPins();
  showToast('Note deleted');
}

async function submitPassphrase() {
  const pass = document.getElementById('passInput').value;
  if (!pass) return;

  const slug = S.artworks[S.current]?.slug;
  const data = S.annotations[slug] || { salt: null };

  if (!data.salt) {
    S.salt     = crypto.getRandomValues(new Uint8Array(16));
    data.salt  = Array.from(S.salt);
  } else {
    S.salt = new Uint8Array(data.salt);
  }

  const testKey = await deriveKey(pass, S.salt);

  if (data.annotations?.length > 0) {
    try { await decryptText(data.annotations[0], testKey); }
    catch(e) {
      showToast('Wrong passphrase', true);
      document.getElementById('passInput').value = '';
      S.pendingPinCoords = null;
      return;
    }
  }

  S.key = testKey;
  document.getElementById('passModal').classList.remove('active');
  document.getElementById('passInput').value = '';

  if (S.pendingPinCoords) {
    createPinEditor(S.pendingPinCoords.x, S.pendingPinCoords.y);
    S.pendingPinCoords = null;
  } else {
    S.pendingAnnotation = false;
    renderPins();
  }
  showToast('Annotations unlocked');
}


function openCompare(leftIdx, rightIdx) {
  S.compareLeftIdx  = leftIdx;
  S.compareRightIdx = rightIdx;
  S.view = 'compare';
  gradientPause();
  location.hash = '#/compare';

  document.getElementById('viewerView').classList.remove('active');
  document.getElementById('compareView').classList.add('active');

  if (!S.osd1) {
    S.osd1 = OpenSeadragon({ id: 'osdCompare1', ...OSD_DEFAULTS });
    S.osd2 = OpenSeadragon({ id: 'osdCompare2', ...OSD_DEFAULTS });

    ['osdCompare1', 'osdCompare2'].forEach(id => {
      document.getElementById(id).addEventListener('wheel', e => {
        if (S.view !== 'compare') return;
        e.preventDefault();
        const viewer = id === 'osdCompare1' ? S.osd1 : S.osd2;
        if (!viewer) return;
        const vp   = viewer.viewport;
        const rect = document.getElementById(id).getBoundingClientRect();
        if (e.ctrlKey) {
          const factor = Math.exp(-e.deltaY * 0.015);
          const pt = vp.pointFromPixel(new OpenSeadragon.Point(e.clientX - rect.left, e.clientY - rect.top));
          vp.zoomBy(factor, pt, true);
        } else {
          const scale = 1 / (vp.getZoom(true) * rect.width);
          vp.panBy(new OpenSeadragon.Point(e.deltaX * scale, e.deltaY * scale), true);
        }
        vp.applyConstraints();
      }, { passive: false });
    });

    let syncing = false;
    function syncViewers(a, b) {
      a.addHandler('zoom', () => {
        if (syncing) return;
        syncing = true;
        b.viewport.zoomTo(a.viewport.getZoom());
        b.viewport.panTo(a.viewport.getCenter());
        syncing = false;
      });
      a.addHandler('pan', () => {
        if (syncing) return;
        syncing = true;
        b.viewport.panTo(a.viewport.getCenter());
        b.viewport.zoomTo(a.viewport.getZoom());
        syncing = false;
      });
    }
    syncViewers(S.osd1, S.osd2);
    syncViewers(S.osd2, S.osd1);
  }

  S.osd1.open(S.artworks[leftIdx].path);
  S.osd2.open(S.artworks[rightIdx].path);

  document.getElementById('compareLabelLeft').textContent  = S.artworks[leftIdx].name;
  document.getElementById('compareLabelRight').textContent = S.artworks[rightIdx].name;

  updateEdges();
}

function toggleCompare() {
  if (S.view === 'compare') { goDesk(); return; }
  if (S.view !== 'viewer')  { showToast('Open an artwork first'); return; }

  
  const grid = document.getElementById('comparePickerGrid');
  grid.innerHTML = '';

  S.artworks.forEach((art, i) => {
    const item = document.createElement('div');
    item.className = 'compare-picker-item' + (i === S.current ? ' selected' : '');
    item.innerHTML = `<img src="${esc(art.thumbnail)}" alt=""><span>${esc(art.name)}</span>`;
    item.addEventListener('click', () => {
      document.getElementById('comparePickerOverlay').classList.remove('active');
      openCompare(S.current, i);
    });
    grid.appendChild(item);
  });

  document.getElementById('comparePickerOverlay').classList.add('active');
}

document.getElementById('comparePickerCancel').addEventListener('click', () => {
  document.getElementById('comparePickerOverlay').classList.remove('active');
});

let divDrag = false;
document.getElementById('compareDivider').addEventListener('mousedown', () => divDrag = true);
document.addEventListener('mousemove', e => {
  if (!divDrag) return;
  const pct = Math.max(20, Math.min(80, (e.clientX / window.innerWidth) * 100));
  document.getElementById('compareLeft').style.flex        = `0 0 ${pct}%`;
  document.getElementById('compareDivider').style.left     = pct + '%';
});
document.addEventListener('mouseup', () => divDrag = false);


let cropStart = null, cropRect = null;

function toggleCrop() {
  if (S.view !== 'viewer') { showToast('Open an artwork first'); return; }
  if (S.pickMode) togglePick();
  S.cropMode = !S.cropMode;
  document.getElementById('cropOverlay').classList.toggle('active', S.cropMode);
  if (!S.cropMode) {
    cropStart = null;
    cropRect  = null;
    document.getElementById('cropMarquee').style.display = 'none';
  }
  showToast(S.cropMode ? 'Drag to select a region' : 'Crop mode off');
}

document.getElementById('cropOverlay').addEventListener('mousedown', e => {
  if (!S.cropMode) return;
  cropStart = { x: e.offsetX, y: e.offsetY };
  const mq = document.getElementById('cropMarquee');
  mq.style.cssText = `display:block; left:${cropStart.x}px; top:${cropStart.y}px; width:0; height:0;`;
});

document.getElementById('cropOverlay').addEventListener('mousemove', e => {
  if (!S.cropMode || !cropStart) return;
  const x = Math.min(cropStart.x, e.offsetX);
  const y = Math.min(cropStart.y, e.offsetY);
  const w = Math.abs(e.offsetX - cropStart.x);
  const h = Math.abs(e.offsetY - cropStart.y);
  const mq = document.getElementById('cropMarquee');
  mq.style.left = x + 'px'; mq.style.top = y + 'px';
  mq.style.width = w + 'px'; mq.style.height = h + 'px';
  cropRect = { x, y, w, h };
});

document.getElementById('cropOverlay').addEventListener('mouseup', () => {
  if (!S.cropMode || !cropRect || cropRect.w < 10 || cropRect.h < 10) {
    cropStart = null; cropRect = null;
    document.getElementById('cropMarquee').style.display = 'none';
    return;
  }

  const sourceCanvas = document.getElementById('osdViewer').querySelector('canvas');
  if (!sourceCanvas) { showToast('Could not capture canvas', true); return; }

  const scaleX = sourceCanvas.width  / sourceCanvas.offsetWidth;
  const scaleY = sourceCanvas.height / sourceCanvas.offsetHeight;
  const out    = document.createElement('canvas');
  out.width    = Math.round(cropRect.w * scaleX);
  out.height   = Math.round(cropRect.h * scaleY);
  out.getContext('2d').drawImage(
    sourceCanvas,
    Math.round(cropRect.x * scaleX), Math.round(cropRect.y * scaleY), out.width, out.height,
    0, 0, out.width, out.height
  );
  // clean up after closed
  out.toBlob(blob => {
    document.getElementById('cropResultImg').src = URL.createObjectURL(blob);
    document.getElementById('cropResult').classList.add('show');
    S.cropBlob = blob;
  }, 'image/jpeg', 0.92);

  cropStart = null; cropRect = null;
  document.getElementById('cropMarquee').style.display = 'none';
});

function downloadCrop() {
  if (!S.cropBlob) return;
  const url = URL.createObjectURL(S.cropBlob);
  const a   = document.createElement('a');
  a.href     = url;
  a.download = S.artworks[S.current].slug + '-crop.jpg';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function closeCropResult() {
  const img = document.getElementById('cropResultImg');
  if (img.src.startsWith('blob:')) URL.revokeObjectURL(img.src);
  img.src = '';
  document.getElementById('cropResult').classList.remove('show');
}


function togglePick() {
  if (S.view !== 'viewer') { showToast('Open an artwork first'); return; }
  if (S.cropMode) toggleCrop();
  S.pickMode = !S.pickMode;
  document.getElementById('viewerView').classList.toggle('pick-mode', S.pickMode);
  document.querySelector('.edge-btn[title="Colour picker"]').classList.toggle('active', S.pickMode);
  if (!S.pickMode) document.getElementById('colourChip').classList.remove('show');
  showToast(S.pickMode ? 'Click any pixel to sample' : 'Colour picker off');
}

document.getElementById('osdViewer').addEventListener('click', e => {
  if (!S.pickMode) return;

  const canvas = document.getElementById('osdViewer').querySelector('canvas');
  if (!canvas) return;

  const rect   = canvas.getBoundingClientRect();
  const scaleX = canvas.width  / rect.width;
  const scaleY = canvas.height / rect.height;
  const px     = Math.round((e.clientX - rect.left) * scaleX);
  const py     = Math.round((e.clientY - rect.top)  * scaleY);

  const scratch = document.createElement('canvas');
  scratch.width = scratch.height = 1;
  scratch.getContext('2d').drawImage(canvas, px, py, 1, 1, 0, 0, 1, 1);
  const [r, g, b] = scratch.getContext('2d').getImageData(0, 0, 1, 1).data;

  const hex = '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('');
  document.getElementById('colourSwatch').style.background = hex;
  document.getElementById('colourHex').textContent = hex;
  document.getElementById('colourRgb').textContent = `rgb(${r}, ${g}, ${b})`;

  const chip = document.getElementById('colourChip');
  chip.classList.add('show');
  chip.style.left = Math.min(e.clientX + 16, window.innerWidth  - 200) + 'px';
  chip.style.top  = Math.min(e.clientY + 16, window.innerHeight -  80) + 'px';
});

document.getElementById('colourCopy').addEventListener('click', () => {
  const hex = document.getElementById('colourHex').textContent;
  navigator.clipboard.writeText(hex).then(() => showToast('Copied ' + hex));
});


function openSearch() {
  S.searchOpen = true;
  document.getElementById('searchOverlay').classList.add('active');
  document.getElementById('searchInput').focus();
}

function closeSearch() {
  S.searchOpen = false;
  document.getElementById('searchOverlay').classList.remove('active');
}

function handleSearch(q) {
  const container = document.getElementById('searchResults');
  if (!q) { container.innerHTML = ''; return; }
  const matches = S.artworks.filter(a =>
    a.name.toLowerCase().includes(q.toLowerCase()) ||
    a.slug.toLowerCase().includes(q.toLowerCase())
  );
  container.innerHTML = '';
  matches.forEach(a => {
    const item = document.createElement('div');
    item.className = 'search-item';
    item.innerHTML = `
      <img src="${esc(a.thumbnail)}" alt="">
      <div>
        <div class="si-title">${esc(a.name)}</div>
        <div class="si-meta">${esc(a.slug)}</div>
      </div>
    `;
    item.addEventListener('click', () => { closeSearch(); openViewer(S.artworks.indexOf(a)); });
    container.appendChild(item);
  });
}


function openUpload() {
  S.uploadOpen = true;
  document.getElementById('uploadOverlay').classList.add('active');
}

function closeUpload() {
  S.uploadOpen = false;
  document.getElementById('uploadOverlay').classList.remove('active');
  document.getElementById('uploadProgress').style.display = 'none';
}

const uploadZone = document.getElementById('uploadZone');
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
  uploadZone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); });
});
uploadZone.addEventListener('dragenter', () => uploadZone.classList.add('dragover'));
uploadZone.addEventListener('dragover',  () => uploadZone.classList.add('dragover'));
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => {
  uploadZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files[0]);
});

function handleUpload(file) {
  if (!file || !file.type.startsWith('image/')) { showToast('Please upload an image', true); return; }
  const fd = new FormData();
  fd.append('image', file);

  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/convert');

  xhr.upload.addEventListener('progress', e => {
    if (!e.lengthComputable) return;
    const p = Math.round(e.loaded / e.total * 100);
    document.getElementById('uploadFill').style.width   = p + '%';
    document.getElementById('uploadTxt').textContent    = p < 100 ? `Uploading... ${p}%` : 'Converting...';
  });

  xhr.addEventListener('load', () => {
    if (xhr.status >= 200 && xhr.status < 300) {
      S.artworks.push(JSON.parse(xhr.responseText));
      renderDesk();
      closeUpload();
      showToast('Artwork added');
    } else {
      let msg = 'Upload failed';
      try { const err = JSON.parse(xhr.responseText); if (err.error) msg = err.error; } catch(x) {}
      showToast(msg, true);
    }
  });

  document.getElementById('uploadProgress').style.display = 'block';
  xhr.send(fd);
}


function updateEdges() {
  const views = {
    desk:    { top: true,  left: false, right: true,  bottom: false },
    viewer:  { top: true,  left: true,  right: true,  bottom: true  },
    compare: { top: true,  left: true,  right: false, bottom: false },
  };
  const vis = views[S.view] || views.desk;
  document.getElementById('edgeTop').classList.toggle('active',    vis.top);
  document.getElementById('edgeLeft').classList.toggle('active',   vis.left);
  document.getElementById('edgeRight').classList.toggle('active',  vis.right);
  document.getElementById('edgeBottom').classList.toggle('active', vis.bottom);

  const isDesk = S.view === 'desk';
  document.getElementById('appTitle').classList.toggle('visible',   isDesk);
  document.getElementById('searchPill').classList.toggle('visible', isDesk);
  document.getElementById('viewerTitle').classList.toggle('show',   S.view === 'viewer');
}

function toggleFullscreen() {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen();
  else document.exitFullscreen();
}

function closeHelp() {
  S.helpOpen = false;
  document.getElementById('helpOverlay').classList.remove('active');
}


document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (document.getElementById('passModal').classList.contains('active')) {
      document.getElementById('passModal').classList.remove('active'); return;
    }
    if (document.getElementById('comparePickerOverlay').classList.contains('active')) {
      document.getElementById('comparePickerOverlay').classList.remove('active'); return;
    }
    if (S.searchOpen)  { closeSearch();    return; }
    if (S.uploadOpen)  { closeUpload();    return; }
    if (S.helpOpen)    { closeHelp();      return; }
    if (S.pickMode)    { togglePick();     return; }
    if (document.getElementById('cropResult').classList.contains('show')) { closeCropResult(); return; }
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') { e.target.blur(); return; }
    goDesk();
    return;
  }

  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

  switch (e.key) {
    case '/': e.preventDefault(); openSearch();      break;
    case 'a': toggleAnnotations(); break;
    case 'c': toggleCompare();     break;
    case 'r': toggleCrop();        break;
    case 'p': togglePick();        break;
    case 'u': openUpload();        break;
    case 'f': toggleFullscreen();  break;
    case 'j': case 'ArrowRight':
      if (S.view === 'viewer' && S.current < S.artworks.length - 1) openViewer(S.current + 1);
      break;
    case 'k': case 'ArrowLeft':
      if (S.view === 'viewer' && S.current > 0) openViewer(S.current - 1);
      break;
    case 'h':
      if (S.view === 'viewer' && S.osd) S.osd.viewport.goHome();
      break;
    case '?':
      S.helpOpen = true;
      document.getElementById('helpOverlay').classList.add('active');
      break;
  }
}, true);


function applyRoute() {
  const hash = location.hash.replace('#', '') || '/';
  if (hash.startsWith('/artwork/')) {
    const slug = hash.replace('/artwork/', '');
    const idx  = S.artworks.findIndex(a => a.slug === slug);
    if (idx !== -1 && S.view !== 'viewer') openViewer(idx);
  } else if (hash === '/compare') {
    if (S.view === 'viewer') toggleCompare();
  } else {
    if (S.view !== 'desk') goDesk();
  }
}
window.addEventListener('hashchange', applyRoute);


document.getElementById('searchOverlay').addEventListener('click', e => {
  if (e.target === document.getElementById('searchOverlay')) closeSearch();
});
document.getElementById('searchInput').addEventListener('input', e => handleSearch(e.target.value));
document.getElementById('searchPill').addEventListener('click', openSearch);

document.getElementById('uploadOverlay').addEventListener('click', e => {
  if (e.target === document.getElementById('uploadOverlay')) closeUpload();
});
document.getElementById('uploadInput').addEventListener('change', e => handleUpload(e.target.files[0]));

document.getElementById('helpOverlay').addEventListener('click', e => {
  if (e.target === document.getElementById('helpOverlay')) closeHelp();
});

document.getElementById('passInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') submitPassphrase();
});
document.querySelector('#passModal button').addEventListener('click', submitPassphrase);

document.querySelector('.btn-download').addEventListener('click', downloadCrop);
document.querySelector('.btn-close').addEventListener('click', closeCropResult);

document.querySelector('[title="Back to desk"]').addEventListener('click', goDesk);
document.querySelector('[title="Annotations"]').addEventListener('click', toggleAnnotations);
document.querySelector('[title="Compare"]').addEventListener('click', toggleCompare);
document.querySelector('[title="Crop"]').addEventListener('click', toggleCrop);
document.querySelector('[title="Colour picker"]').addEventListener('click', togglePick);
document.querySelector('[title="Upload"]').addEventListener('click', openUpload);
document.querySelector('[title="Fullscreen"]').addEventListener('click', toggleFullscreen);


async function init() {
  initGradient();
  try {
    S.artworks = await api('/api/artworks');
  } catch(e) {
    showToast('Failed to load artworks', true);
  }
  renderDesk();
  updateEdges();
  applyRoute();
}

init();
