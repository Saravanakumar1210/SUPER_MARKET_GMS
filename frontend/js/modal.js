let modalOpen = false;
let modalProduct = null;
let focusableElements = [];
let firstFocusable = null;
let lastFocusable = null;
let modalQty = 1;

function getModalBasketState(productName) {
    const inBasket = typeof GmsShoppingStore !== 'undefined'
        && GmsShoppingStore.isInCart(productName);
    const qty = inBasket && typeof GmsShoppingStore !== 'undefined'
        ? GmsShoppingStore.getCartQty(productName) : 0;
    return { inBasket, qty };
}

function getModalAddBtnLabel(product) {
    const { inBasket } = getModalBasketState(product.productName);
    const name = product.displayName;

    if (inBasket) {
        return {
            label: `${modalQty} in basket`,
            ariaLabel: `${name} — ${modalQty} in basket`
        };
    }

    return {
        label: modalQty === 1 ? 'Add to basket' : `Add ${modalQty} to basket`,
        ariaLabel: modalQty === 1
            ? `Add ${name} to basket`
            : `Add ${modalQty} of ${name} to basket`
    };
}

function updateModalAddBtnLabel(product) {
    const addBtn = document.getElementById('modal-add-btn');
    if (!addBtn || !product) return;

    const { inBasket } = getModalBasketState(product.productName);
    const { label, ariaLabel } = getModalAddBtnLabel(product);

    addBtn.setAttribute('aria-label', ariaLabel);
    addBtn.classList.toggle('modal-add-btn--in-basket', inBasket);
    addBtn.innerHTML = `<i class="fa-solid fa-basket-shopping" aria-hidden="true"></i> ${label}`;
}

function buildModalQtyHTML() {
    return `
        <div class="modal-qty-wrap" role="group" aria-label="Quantity in basket">
            <span class="modal-qty-display" id="modal-qty-display">${modalQty}</span>
            <div class="modal-qty-btns">
                <button type="button" class="modal-qty-btn" id="modal-qty-up" aria-label="Increase quantity">
                    <i class="fa-solid fa-chevron-up" aria-hidden="true"></i>
                </button>
                <button type="button" class="modal-qty-btn" id="modal-qty-down" aria-label="Decrease quantity">
                    <i class="fa-solid fa-chevron-down" aria-hidden="true"></i>
                </button>
            </div>
        </div>
    `;
}

function buildModalActionsHTML(product) {
    const { inBasket } = getModalBasketState(product.productName);
    const { label, ariaLabel } = getModalAddBtnLabel(product);
    const name = product.displayName;
    const inBasketClass = inBasket ? ' modal-add-btn--in-basket' : '';

    const removeBtn = inBasket ? `
        <button type="button" class="modal-remove-btn" id="modal-remove-btn"
            aria-label="Remove ${name} from basket">
            <i class="fa-solid fa-xmark" aria-hidden="true"></i>
        </button>
    ` : '';

    return `
        ${buildModalQtyHTML()}
        <button type="button" class="modal-add-btn${inBasketClass}" id="modal-add-btn"
            aria-label="${ariaLabel}">
            <i class="fa-solid fa-basket-shopping" aria-hidden="true"></i>
            ${label}
        </button>
        ${removeBtn}
    `;
}

function bindModalActions(product) {
    const qtyDisplay = document.getElementById('modal-qty-display');
    const qtyUp      = document.getElementById('modal-qty-up');
    const qtyDown    = document.getElementById('modal-qty-down');
    const addBtn     = document.getElementById('modal-add-btn');
    const removeBtn  = document.getElementById('modal-remove-btn');

    if (qtyUp && qtyDisplay) {
        qtyUp.addEventListener('click', () => {
            modalQty = Math.min(modalQty + 1, 99);
            qtyDisplay.textContent = modalQty;
            updateModalAddBtnLabel(product);
        });
    }
    if (qtyDown && qtyDisplay) {
        qtyDown.addEventListener('click', () => {
            modalQty = Math.max(modalQty - 1, 1);
            qtyDisplay.textContent = modalQty;
            updateModalAddBtnLabel(product);
        });
    }

    addBtn?.addEventListener('click', () => {
        const { inBasket } = getModalBasketState(product.productName);
        if (inBasket) {
            if (typeof setCartQuantity !== 'function') return;
            setCartQuantity(product.productName, modalQty);
        } else {
            if (typeof addToCart !== 'function') return;
            addToCart(product.productName, modalQty);
        }
        if (typeof updateHeaderBadges === 'function') updateHeaderBadges();
        if (typeof updateProductCardBasketState === 'function') {
            updateProductCardBasketState(product.productName);
        }
        if (typeof addToRecentlyViewed === 'function') addToRecentlyViewed(product);
        refreshModalBasketUI();
    });

    removeBtn?.addEventListener('click', () => {
        if (typeof removeFromCart === 'function') removeFromCart(product.productName);
        if (typeof updateHeaderBadges === 'function') updateHeaderBadges();
        if (typeof updateProductCardBasketState === 'function') {
            updateProductCardBasketState(product.productName);
        }
        modalQty = 1;
        refreshModalBasketUI();
    });
}

function refreshModalBasketUI() {
    if (!modalOpen || !modalProduct) return;

    const actionsRow = document.getElementById('modal-actions-row');
    if (!actionsRow) return;

    const { inBasket, qty } = getModalBasketState(modalProduct.productName);
    if (inBasket) modalQty = qty;
    else modalQty = Math.max(1, modalQty);

    actionsRow.innerHTML = buildModalActionsHTML(modalProduct);
    bindModalActions(modalProduct);

    const modal = document.getElementById('product-modal');
    if (modal) trapFocus(modal);
}

function openProductModal(product) {
    ensureProductModalShell();
    const overlay = document.getElementById('product-modal-overlay');
    const modal   = document.getElementById('product-modal');
    if (!overlay || !modal) return;

    modalProduct = product;
    const { inBasket, qty } = getModalBasketState(product.productName);
    modalQty = inBasket ? qty : 1;

    const reviews  = typeof getProductCardReviewCount === 'function'
        ? getProductCardReviewCount(product, 0, 0)
        : 12;
    const category = normalizeCategoryName(product.categoryName);
    const subCat   = product.subCategoryName ? normalizeCategoryName(product.subCategoryName) : null;
    const skuCode  = 'GMS-' + String(product.productId || '').padStart(5, '0');

    const catLink  = `<a href="products.html?category=${encodeURIComponent(product.categoryName)}">${category}</a>`;
    const subLink  = subCat
        ? `, <a href="products.html?subcategory=${encodeURIComponent(product.subCategoryName)}">${subCat}</a>`
        : '';

    const descHTML = product.productDescription
        ? `<p class="modal-description">${product.productDescription.split('\n').filter(Boolean).slice(0, 2).join(' ')}</p>`
        : `<p class="modal-description">${product.displayName} — available at GMS World Foods, West Drayton. Contact us on WhatsApp to order.</p>`;

    const discountPct = parseInt(product.discountPercent, 10) || 0;
    const discountBadge = typeof buildDiscountBadgeHTML === 'function'
        ? buildDiscountBadgeHTML(discountPct, 'discount-circle--modal')
        : '';

    modal.innerHTML = `
        <button class="modal-close" id="modal-close-btn" aria-label="Close product details">
            <i class="fa-solid fa-xmark" aria-hidden="true"></i>
        </button>

        <div class="modal-body">

            <div class="modal-image-col">
                <div class="modal-thumb-strip" id="modal-thumb-strip">
                    <div class="modal-thumb active" data-index="0">
                        ${renderProductImageArea(product, 'thumb')}
                    </div>
                </div>
                <div class="modal-main-image-wrap" id="modal-main-image">
                    ${discountBadge}
                    ${renderProductImageArea(product, 'modal-main')}
                </div>
            </div>

            <div class="modal-details-col">
                <h2 id="modal-product-name" class="modal-title">${product.displayName}</h2>

                <div class="modal-rating-row" aria-label="5 out of 5 stars, ${reviews} reviews">
                    <span class="modal-rating-stars">
                        <i class="fa-solid fa-star"></i>
                        <i class="fa-solid fa-star"></i>
                        <i class="fa-solid fa-star"></i>
                        <i class="fa-solid fa-star"></i>
                        <i class="fa-solid fa-star"></i>
                    </span>
                    <span class="modal-rating-count">(${reviews} reviews)</span>
                </div>

                ${descHTML}

                <div class="modal-availability">
                    <span>Availability:</span>
                    <span class="modal-availability-value">
                        <i class="fa-solid fa-circle-check" aria-hidden="true"></i> Enquire on WhatsApp
                    </span>
                </div>

                <div class="modal-actions-row" id="modal-actions-row">
                    ${buildModalActionsHTML(product)}
                </div>

                <div class="modal-meta">
                    <div class="modal-meta-row">
                        <span class="modal-meta-label">SKU:</span>
                        <span class="modal-meta-value">${skuCode}</span>
                    </div>
                    <div class="modal-meta-row">
                        <span class="modal-meta-label">Categories:</span>
                        <span class="modal-meta-value">${catLink}${subLink}</span>
                    </div>
                    ${product.packType ? `
                    <div class="modal-meta-row">
                        <span class="modal-meta-label">Pack Type:</span>
                        <span class="modal-meta-value">${product.packType}</span>
                    </div>` : ''}
                    ${product.weightKG !== null && product.weightKG !== undefined ? `
                    <div class="modal-meta-row">
                        <span class="modal-meta-label">Weight:</span>
                        <span class="modal-meta-value">${product.weightKG} kg</span>
                    </div>` : ''}
                </div>
            </div>
        </div>

    `;

    modal.dataset.productName = product.productName;

    overlay.classList.add('open');
    modal.classList.add('open');
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'modal-product-name');
    document.body.classList.add('modal-open');
    modalOpen = true;

    document.getElementById('modal-close-btn').addEventListener('click', closeProductModal);
    overlay.addEventListener('click', onOverlayClick);

    bindModalActions(product);

    trapFocus(modal);
    document.getElementById('modal-close-btn').focus();
}

function closeProductModal() {
    const overlay = document.getElementById('product-modal-overlay');
    const modal   = document.getElementById('product-modal');
    if (!overlay || !modal) return;

    modal.classList.remove('open');
    overlay.classList.remove('open');
    document.body.classList.remove('modal-open');
    modalOpen = false;
    modalProduct = null;
    modalQty  = 1;

    overlay.removeEventListener('click', onOverlayClick);
    document.removeEventListener('keydown', onModalKeydown);

    const trigger = getLastTriggerElement ? getLastTriggerElement() : null;
    if (trigger) trigger.focus();
}

function onOverlayClick(e) {
    if (e.target === document.getElementById('product-modal-overlay')) {
        closeProductModal();
    }
}

function onModalKeydown(e) {
    if (!modalOpen) return;

    if (e.key === 'Escape') {
        closeProductModal();
        return;
    }

    if (e.key === 'Tab') {
        if (!firstFocusable || !lastFocusable) return;
        if (e.shiftKey) {
            if (document.activeElement === firstFocusable) {
                e.preventDefault();
                lastFocusable.focus();
            }
        } else {
            if (document.activeElement === lastFocusable) {
                e.preventDefault();
                firstFocusable.focus();
            }
        }
    }
}

function trapFocus(modal) {
    focusableElements = modal.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    firstFocusable = focusableElements[0];
    lastFocusable  = focusableElements[focusableElements.length - 1];
    document.addEventListener('keydown', onModalKeydown);
}

function ensureProductModalShell() {
    if (document.getElementById('product-modal-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'product-modal-overlay';
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div id="product-modal" class="product-modal" role="dialog" aria-modal="true"></div>
    `;
    document.body.appendChild(overlay);
}

function initModal() {
    ensureProductModalShell();
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modalOpen) closeProductModal();
    });

    const onBasketChange = () => {
        if (!modalOpen || !modalProduct) return;
        refreshModalBasketUI();
        if (typeof updateProductCardBasketState === 'function') {
            updateProductCardBasketState(modalProduct.productName);
        }
    };
    document.addEventListener('gms:basket-updated', onBasketChange);
    document.addEventListener('gms:cart-updated', onBasketChange);
}
