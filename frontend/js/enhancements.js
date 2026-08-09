/* ============================================================
   GMS WORLD FOODS — ENHANCEMENTS
   Recently viewed, mobile filters, URL sync, skeleton loading, etc.
   ============================================================ */

const RECENT_KEY  = 'gms_recent_v1';
const MAX_RECENT  = 8;

function addToRecentlyViewed(product) {
    try {
        const list = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
        const filtered = list.filter(p => p.productName !== product.productName);
        filtered.unshift({
            productName:  product.productName,
            displayName:  product.displayName,
            categoryName: product.categoryName
        });
        localStorage.setItem(RECENT_KEY, JSON.stringify(filtered.slice(0, MAX_RECENT)));
    } catch (e) { /* storage may be blocked */ }
}

function getRecentlyViewed() {
    try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]'); }
    catch (e) { return []; }
}

function renderRecentlyViewed() {
    const section = document.getElementById('recently-viewed-section');
    const strip   = document.getElementById('recently-viewed-strip');
    if (!section || !strip) return;

    const recent = getRecentlyViewed();
    if (recent.length === 0) { section.classList.add('hidden'); return; }

    section.classList.remove('hidden');
    strip.className = 'fp-grid';
    strip.innerHTML = recent.map((p, index) => {
        const product = ALL_PRODUCTS.find(ap => ap.productName === p.productName) || p;
        return buildProductCardHTML(product, index, 0);
    }).join('');

    bindProductCards(strip);
}

function updateProductCardBasketState(productName, card) {
    const cards = card ? [card] : Array.from(
        document.querySelectorAll(`.fp-card[data-product-name="${CSS.escape(productName)}"]`)
    );
    const inBasket = typeof GmsShoppingStore !== 'undefined'
        && GmsShoppingStore.isInCart(productName);
    const qty    = inBasket && typeof GmsShoppingStore !== 'undefined'
        ? GmsShoppingStore.getCartQty(productName) : 0;

    cards.forEach(c => {
        const product = typeof ALL_PRODUCTS !== 'undefined'
            ? ALL_PRODUCTS.find(p => p.productName === productName)
            : null;
        if (!product || typeof buildProductCardBottomHTML !== 'function') return;

        const existingBottom = c.querySelector('.fp-bottom');
        if (existingBottom) {
            const temp = document.createElement('div');
            temp.innerHTML = buildProductCardBottomHTML(product, inBasket, qty).trim();
            existingBottom.replaceWith(temp.firstElementChild);
        }
    });
}

function updateHeaderBadges() {
    const basketEl = document.getElementById('basket-count')
        || document.getElementById('bucket-count')
        || document.getElementById('cart-count');
    if (basketEl) {
        const count = typeof getCartCount === 'function' ? getCartCount() : 0;
        basketEl.textContent = count;
        basketEl.classList.toggle('visible', count > 0);
    }
}

/** Auto-scrolling horizontal product strip (home Hot Offers, basket recommendations, etc.) */
const fpGridScrollTimers = new Map();

function stripFpGridClones(grid) {
    grid.querySelectorAll('.fp-card[data-fp-clone="1"]').forEach(el => el.remove());
}

/** Duplicate strip cards so scrolling can loop seamlessly (circular carousel). */
function setupFpGridInfiniteLoop(grid) {
    stripFpGridClones(grid);

    const originals = Array.from(grid.querySelectorAll('.fp-card:not([data-fp-clone="1"])'));
    if (originals.length < 2) {
        delete grid.dataset.fpLoopWidth;
        return 0;
    }

    const fragment = document.createDocumentFragment();
    originals.forEach(card => {
        const clone = card.cloneNode(true);
        clone.setAttribute('data-fp-clone', '1');
        clone.setAttribute('aria-hidden', 'true');
        clone.setAttribute('tabindex', '-1');
        fragment.appendChild(clone);
    });
    grid.appendChild(fragment);

    const firstClone = grid.querySelector('.fp-card[data-fp-clone="1"]');
    const loopWidth = firstClone ? firstClone.offsetLeft - originals[0].offsetLeft : 0;
    if (loopWidth > 0) grid.dataset.fpLoopWidth = String(loopWidth);
    else delete grid.dataset.fpLoopWidth;
    return loopWidth;
}

function normalizeFpGridScroll(grid) {
    const loopWidth = parseFloat(grid.dataset.fpLoopWidth || '0', 10);
    if (!loopWidth || grid.scrollLeft < loopWidth - 2) return;

    const snap = grid.style.scrollSnapType;
    grid.style.scrollSnapType = 'none';
    grid.style.scrollBehavior = 'auto';
    grid.scrollLeft -= loopWidth;
    grid.style.scrollBehavior = '';
    grid.style.scrollSnapType = snap;
}

function initFpGridAutoScroll(gridOrId, options = {}) {
    const grid = typeof gridOrId === 'string' ? document.getElementById(gridOrId) : gridOrId;
    if (!grid) return;

    const timerKey = grid.id || grid;
    const minCards = options.minCards ?? 7;
    const interval = options.intervalMs ?? 2000;

    if (fpGridScrollTimers.has(timerKey)) {
        clearInterval(fpGridScrollTimers.get(timerKey));
        fpGridScrollTimers.delete(timerKey);
    }

    stripFpGridClones(grid);

    const cards = grid.querySelectorAll('.fp-card:not([data-fp-clone="1"])');
    if (cards.length < minCards) return;

    const loopWidth = setupFpGridInfiniteLoop(grid);
    if (loopWidth <= 0) return;

    const getScrollStep = () => {
        const card = grid.querySelector('.fp-card:not([data-fp-clone="1"])');
        if (!card) return 280;
        const gap = parseFloat(getComputedStyle(grid).columnGap || getComputedStyle(grid).gap) || 20;
        return card.offsetWidth + gap;
    };

    const scrollNext = () => {
        const step = getScrollStep();
        grid.scrollBy({ left: step, behavior: 'smooth' });
    };

    if (!grid.dataset.fpLoopScrollBound) {
        grid.addEventListener('scroll', () => normalizeFpGridScroll(grid), { passive: true });
        grid.dataset.fpLoopScrollBound = '1';
    }

    const startAutoplay = () => {
        if (fpGridScrollTimers.has(timerKey)) clearInterval(fpGridScrollTimers.get(timerKey));
        fpGridScrollTimers.set(timerKey, setInterval(scrollNext, interval));
    };

    const stopAutoplay = () => {
        if (fpGridScrollTimers.has(timerKey)) {
            clearInterval(fpGridScrollTimers.get(timerKey));
            fpGridScrollTimers.delete(timerKey);
        }
    };

    if (!grid.dataset.stripCarouselBound) {
        grid.addEventListener('mouseenter', stopAutoplay);
        grid.addEventListener('mouseleave', startAutoplay);
        grid.addEventListener('touchstart', stopAutoplay, { passive: true });
        grid.addEventListener('touchend', startAutoplay, { passive: true });
        grid.dataset.stripCarouselBound = 'true';
    }

    startAutoplay();
}

let mobileFilterBound = false;

function initMobileFilterDrawer() {
    if (mobileFilterBound) return;

    const triggerBtn = document.getElementById('mobile-filter-btn');
    const sheet      = document.getElementById('mobile-filter-sheet');
    const sheetBody  = document.getElementById('mobile-filter-body');
    const overlay    = document.getElementById('mobile-filter-overlay');
    const closeBtn   = document.getElementById('mobile-filter-close');
    const sidebar    = document.querySelector('nav.catalog-sidebar')
        || document.querySelector('.catalog-sidebar.filter-panel')
        || document.querySelector('.catalog-sidebar');
    const catalogLayout = document.querySelector('.catalog-layout');

    if (!triggerBtn || !sidebar || !overlay) return;
    mobileFilterBound = true;

    const open = (e) => {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }

        /* Prefer dedicated left sheet host so the panel is always visible */
        if (sheet && sheetBody) {
            if (sidebar.parentElement !== sheetBody) {
                sheetBody.appendChild(sidebar);
            }
            sidebar.classList.add('mobile-filter-open');
            sidebar.style.cssText = [
                'display:flex',
                'flex-direction:column',
                'position:relative',
                'transform:none',
                'width:100%',
                'max-width:100%',
                'height:100%',
                'max-height:none',
                'visibility:visible',
                'opacity:1',
                'inset:auto',
                'z-index:1',
                'border:none',
                'border-radius:0',
                'box-shadow:none',
            ].join(';');
            sheet.classList.add('open');
            sheet.setAttribute('aria-hidden', 'false');
        } else {
            sidebar.classList.add('mobile-filter-open');
        }

        overlay.classList.add('open');
        document.body.classList.add('drawer-open');
        triggerBtn.setAttribute('aria-expanded', 'true');
        if (typeof updateFilterSidebarMeta === 'function') updateFilterSidebarMeta();
    };

    const close = () => {
        overlay.classList.remove('open');
        document.body.classList.remove('drawer-open');
        triggerBtn.setAttribute('aria-expanded', 'false');

        if (sheet) {
            sheet.classList.remove('open');
            sheet.setAttribute('aria-hidden', 'true');
        }

        sidebar.classList.remove('mobile-filter-open');
        sidebar.style.cssText = '';

        /* Put sidebar back into catalog layout for desktop resize */
        if (catalogLayout && sidebar.parentElement !== catalogLayout) {
            const main = catalogLayout.querySelector('.catalog-main');
            if (main) catalogLayout.insertBefore(sidebar, main);
            else catalogLayout.prepend(sidebar);
        }
    };

    triggerBtn.setAttribute('aria-expanded', 'false');
    triggerBtn.setAttribute('aria-controls', 'mobile-filter-sheet');
    if (sheet) sheet.setAttribute('aria-hidden', 'true');

    triggerBtn.addEventListener('click', open);
    closeBtn && closeBtn.addEventListener('click', (e) => {
        e.preventDefault();
        close();
    });
    overlay.addEventListener('click', close);

    /* Close affordance inside the filter ticket header */
    if (!sidebar.querySelector('.mobile-filter-panel-close')) {
        const head = sidebar.querySelector('.filter-panel-ticket');
        if (head) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'mobile-filter-panel-close drawer-close';
            btn.setAttribute('aria-label', 'Close filters');
            btn.innerHTML = '<i class="fa-solid fa-xmark" aria-hidden="true"></i>';
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                close();
            });
            head.appendChild(btn);
        }
    }
}

function initStickyToolbar() {
    const toolbar = document.querySelector('.catalog-toolbar');
    if (!toolbar) return;

    if (window.matchMedia('(max-width: 767px)').matches) {
        toolbar.classList.remove('toolbar-sticky');
        return;
    }

    const sentinel = document.createElement('div');
    sentinel.style.height = '1px';
    toolbar.parentNode.insertBefore(sentinel, toolbar);

    const headerH = getComputedStyle(document.documentElement)
        .getPropertyValue('--header-h').trim() || '68px';

    const obs = new IntersectionObserver(entries => {
        entries.forEach(e => {
            toolbar.classList.toggle('toolbar-sticky', !e.isIntersecting);
        });
    }, { rootMargin: `-${headerH} 0px 0px 0px` });

    obs.observe(sentinel);
}

function pushFilterState() {
    if (typeof history === 'undefined' || !history.replaceState) return;
    const params = new URLSearchParams(window.location.search);

    if (filterState.selectedCategories.length === 1) {
        params.set('category', filterState.selectedCategories[0]);
    } else {
        params.delete('category');
    }

    if (filterState.selectedSubCategories.length === 1) {
        params.set('subcategory', filterState.selectedSubCategories[0]);
    } else {
        params.delete('subcategory');
    }

    if (filterState.selectedCultures.length) {
        params.set('culture', filterState.selectedCultures.join(','));
    } else {
        params.delete('culture');
    }

    if (filterState.searchQuery.trim()) {
        params.set('search', filterState.searchQuery.trim());
    } else {
        params.delete('search');
    }

    if (filterState.spotlightSection) {
        params.set('section', filterState.spotlightSection);
    } else {
        params.delete('section');
    }

    if (filterState.sortBy && filterState.sortBy !== 'none') {
        params.set('sort', filterState.sortBy);
    } else {
        params.delete('sort');
    }

    if (filterState.perPage && filterState.perPage !== 96) {
        params.set('perPage', String(filterState.perPage));
    } else {
        params.delete('perPage');
    }

    const qs = params.toString();
    history.replaceState(null, '', qs ? `${location.pathname}?${qs}` : location.pathname);
}

function updatePageMeta() {
    if (document.body.dataset.page !== 'products') return;

    const cats  = filterState.selectedCategories;
    const query = filterState.searchQuery.trim();
    const total = typeof cachedTotalCount !== 'undefined' ? cachedTotalCount : 0;

    let title = 'Products — GMS World Foods Ltd';
    let desc  = `Browse ${total.toLocaleString()} products at GMS World Foods Ltd, West Drayton. Order via WhatsApp.`;

    if (cats.length === 1) {
        const name = normalizeCategoryName(cats[0]);
        title = `${name} — GMS World Foods Ltd`;
        desc  = `Browse ${total.toLocaleString()} ${name} products at GMS World Foods Ltd. Order via WhatsApp.`;
    } else if (filterState.spotlightSection && typeof SPOTLIGHT_FILTERS !== 'undefined') {
        const spotlight = SPOTLIGHT_FILTERS.find(s => s.key === filterState.spotlightSection);
        if (spotlight) {
            title = `${spotlight.label} — GMS World Foods Ltd`;
            desc  = `Browse ${total.toLocaleString()} ${spotlight.label.toLowerCase()} at GMS World Foods Ltd. Order via WhatsApp.`;
        }
    } else if (filterState.selectedCultures.length === 1 && typeof getCultureLabel === 'function') {
        const name = getCultureLabel(filterState.selectedCultures[0]);
        title = `${name} culture — GMS World Foods Ltd`;
        desc  = `Browse ${total.toLocaleString()} ${name} culture products at GMS World Foods Ltd. Order via WhatsApp.`;
    } else if (filterState.selectedCultures.length > 1) {
        title = 'World cultures — GMS World Foods Ltd';
        desc  = `Browse ${total.toLocaleString()} curated culture products at GMS World Foods Ltd. Order via WhatsApp.`;
    } else if (query) {
        title = `"${query}" — GMS World Foods Ltd`;
        desc  = `${total.toLocaleString()} results for "${query}" at GMS World Foods Ltd.`;
    }

    document.title = title;
    const metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc) metaDesc.setAttribute('content', desc);
}

function renderSkeletonGrid(count) {
    const grid = document.getElementById('product-grid');
    if (!grid) return;

    grid.innerHTML = Array.from({ length: count }, () => `
        <article class="fp-card skeleton-card" aria-hidden="true">
            <div class="fp-image-area">
                <div class="skeleton skeleton-image fp-skeleton-image"></div>
            </div>
            <div class="fp-content">
                <div class="skeleton skeleton-badge"></div>
                <div class="skeleton skeleton-title"></div>
            </div>
        </article>
    `).join('');
}

function checkDataLoaded() {
    const loaded = typeof ALL_PRODUCTS !== 'undefined' && ALL_PRODUCTS.length > 0;
    if (!loaded) {
        const grid = document.getElementById('product-grid');
        if (grid) {
            grid.innerHTML = `
                <div class="no-results">
                    <i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i>
                    <p>Products could not be loaded. Please ensure the server is running and refresh the page.</p>
                    <button class="btn btn-primary" onclick="location.reload()">
                        <i class="fa-solid fa-rotate-right"></i> Refresh
                    </button>
                </div>`;
        }
        return false;
    }
    return true;
}

function onFiltersApplied() {
    pushFilterState();
    updatePageMeta();
}

