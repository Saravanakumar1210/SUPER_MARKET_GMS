/* Category thumbnail images for top-categories carousel (from Cloudinary / API). */
const CATEGORY_IMAGE_MAP = {
    'Dry grocery & staples':          'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170663/gms-world-foods/category%20images/dry-grocery-staples.png',
    'Snacks & confectionery':         'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170666/gms-world-foods/category%20images/snacks-confectionery.png',
    'Beverages':                      'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170669/gms-world-foods/category%20images/beverages.png',
    'Fresh produce':                  'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170671/gms-world-foods/category%20images/fresh-produce.png',
    'Frozen, meat & ready-to-cook':   'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170673/gms-world-foods/category%20images/frozen-meat-ready-to-cook.png',
    'Condiments, sauces & pickles':   'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170675/gms-world-foods/category%20images/condiments-sauces-pickles.png',
    'Dairy, eggs & chilled':          'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170677/gms-world-foods/category%20images/dairy-eggs-chilled.png',
    'Household & personal care':      'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170680/gms-world-foods/category%20images/household-personal-care.png',
    'Bakery, pasta & noodles':        'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170681/gms-world-foods/category%20images/bakery-pasta-noodles.png',
    DEFAULT:                          'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170663/gms-world-foods/category%20images/dry-grocery-staples.png'
};

const CATEGORY_BANNER_IMAGE_MAP = {
    'Dry grocery & staples':          'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170663/gms-world-foods/category%20images/dry-grocery-staples.png',
    'Snacks & confectionery':         'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170666/gms-world-foods/category%20images/snacks-confectionery.png',
    'Beverages':                      'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170669/gms-world-foods/category%20images/beverages.png',
    'Fresh produce':                  'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170671/gms-world-foods/category%20images/fresh-produce.png',
    'Frozen, meat & ready-to-cook':   'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170673/gms-world-foods/category%20images/frozen-meat-ready-to-cook.png',
    'Condiments, sauces & pickles':   'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170675/gms-world-foods/category%20images/condiments-sauces-pickles.png',
    'Dairy, eggs & chilled':          'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170677/gms-world-foods/category%20images/dairy-eggs-chilled.png',
    'Household & personal care':      'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170680/gms-world-foods/category%20images/household-personal-care.png',
    'Bakery, pasta & noodles':        'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170681/gms-world-foods/category%20images/bakery-pasta-noodles.png',
    DEFAULT:                          'https://res.cloudinary.com/dgsnwhyah/image/upload/v1783170663/gms-world-foods/category%20images/dry-grocery-staples.png'
};

/* Category colour + icon config for product cards without a DB image path */
const CATEGORY_PLACEHOLDER_CONFIG = {
    'Dry grocery & staples':          { color: '#185FA5', icon: 'fa-wheat-awn' },
    'Snacks & confectionery':         { color: '#D85A30', icon: 'fa-cookie-bite' },
    'Beverages':                      { color: '#1D9E75', icon: 'fa-bottle-water' },
    'Fresh produce':                  { color: '#3B6D11', icon: 'fa-leaf' },
    'Frozen, meat & ready-to-cook':   { color: '#534AB7', icon: 'fa-snowflake' },
    'Condiments, sauces & pickles':   { color: '#BA7517', icon: 'fa-jar' },
    'Dairy, eggs & chilled':          { color: '#0891B2', icon: 'fa-cheese' },
    'Household & personal care':      { color: '#993556', icon: 'fa-pump-soap' },
    'Bakery, pasta & noodles':        { color: '#5F5E5A', icon: 'fa-bread-slice' },
    DEFAULT:                          { color: '#475569', icon: 'fa-tag' }
};

function getCategoryKey(categoryName) {
    if (!categoryName) return 'DEFAULT';
    if (CATEGORY_PLACEHOLDER_CONFIG[categoryName]) return categoryName;
    // Case-insensitive fallback
    const lower = categoryName.toLowerCase();
    for (const key of Object.keys(CATEGORY_PLACEHOLDER_CONFIG)) {
        if (key.toLowerCase() === lower) return key;
    }
    return 'DEFAULT';
}

function categoryStatForName(categoryName) {
    if (typeof getCategoryStats !== 'function') return null;
    const key = getCategoryKey(categoryName);
    return getCategoryStats().find(s => getCategoryKey(s.CategoryName) === key) || null;
}

function getCategoryImage(categoryName) {
    const stat = categoryStatForName(categoryName);
    if (stat && stat.IconImageUrl) return stat.IconImageUrl;
    const key = getCategoryKey(categoryName);
    return CATEGORY_IMAGE_MAP[key] || CATEGORY_IMAGE_MAP.DEFAULT;
}

function getCategoryBannerImage(categoryName) {
    const stat = categoryStatForName(categoryName);
    if (stat && stat.BannerImageUrl) return stat.BannerImageUrl;
    const key = getCategoryKey(categoryName);
    return CATEGORY_BANNER_IMAGE_MAP[key] || CATEGORY_BANNER_IMAGE_MAP.DEFAULT;
}

function renderCategoryCardImageHTML(categoryName) {
    const name = typeof normalizeCategoryName === 'function'
        ? normalizeCategoryName(categoryName)
        : categoryName;
    const src = getCategoryImage(categoryName);
    const ph = getCategoryPlaceholder(categoryName);
    return `<img src="${src}" alt="${name}" class="top-cat-card-img" loading="lazy" decoding="async"
        onerror="this.onerror=null;this.classList.add('top-cat-card-img--hidden');this.insertAdjacentHTML('afterend','<i class=\\'fa-solid ${ph.icon} top-cat-card-fallback-icon\\' aria-hidden=\\'true\\'></i>');this.parentElement.style.background='${ph.gradient}';this.parentElement.classList.add('top-cat-card-image--fallback');">`;
}

function getCategoryPlaceholder(categoryName) {
    const key = getCategoryKey(categoryName);
    const config = CATEGORY_PLACEHOLDER_CONFIG[key] || CATEGORY_PLACEHOLDER_CONFIG.DEFAULT;
    const baseColor = config.color;
    const darker = adjustColor(baseColor, -30);
    return {
        color: baseColor,
        icon: config.icon,
        gradient: `linear-gradient(135deg, ${baseColor} 0%, ${darker} 100%)`
    };
}

function adjustColor(hex, amount) {
    const num = parseInt(hex.replace('#', ''), 16);
    let r = (num >> 16) + amount;
    let g = ((num >> 8) & 0x00ff) + amount;
    let b = (num & 0x0000ff) + amount;
    r = Math.max(0, Math.min(255, r));
    g = Math.max(0, Math.min(255, g));
    b = Math.max(0, Math.min(255, b));
    return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
}

function getProductInitials(productName) {
    if (!productName) return '';
    const words = productName.trim().split(/\s+/);
    if (words.length >= 2) {
        return (words[0][0] + words[1][0]).toUpperCase();
    }
    return productName.slice(0, 2).toUpperCase();
}

function resolveProductImageUrl(product) {
    if (!product) return null;

    const directUrl = (product.primaryImageUrl || '').trim();
    if (directUrl) return directUrl;

    if (product.productId != null && typeof PRODUCT_IMAGE_BY_ID !== 'undefined') {
        const mapped = PRODUCT_IMAGE_BY_ID[product.productId] || PRODUCT_IMAGE_BY_ID[String(product.productId)];
        if (mapped) return mapped;
    }

    return null;
}

function escapeHtmlAttr(str) {
    return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;');
}

function renderPlaceholderHTML(categoryName, productName, sizeClass) {
    const placeholder = getCategoryPlaceholder(categoryName);
    const initials = getProductInitials(productName);
    const iconSize = sizeClass === 'large' ? '64px' : sizeClass === 'small' ? '32px' : '48px';
    return `
        <div class="product-placeholder ${sizeClass || ''}" style="background: ${placeholder.gradient}" aria-hidden="true">
            <i class="fa-solid ${placeholder.icon}" style="font-size: ${iconSize}"></i>
            <span class="placeholder-initials">${initials}</span>
        </div>
    `;
}

function renderProductImageArea(product, sizeClass) {
    const primaryUrl = resolveProductImageUrl(product);
    if (!primaryUrl) {
        return renderPlaceholderHTML(product.categoryName, product.productName, sizeClass);
    }

    const cls = `product-image ${sizeClass || ''}`.trim();
    const alt = escapeHtmlAttr(product.displayName || product.productName);
    const iconFallbackAttr = ` data-icon-fallback="1" data-category="${escapeHtmlAttr(product.categoryName)}" data-name="${escapeHtmlAttr(product.productName)}" data-size="${escapeHtmlAttr(sizeClass || '')}"`;

    return `<img src="${escapeHtmlAttr(primaryUrl)}" alt="${alt}" class="${cls}" loading="lazy" decoding="async"${iconFallbackAttr}
        onerror="window.__gmsProductImgError && window.__gmsProductImgError(this)">`;
}

function handleProductImageError(img) {
    if (!img) return;
    if (img.dataset.iconFallback && typeof renderPlaceholderHTML === 'function') {
        img.onerror = null;
        const html = renderPlaceholderHTML(
            img.dataset.category,
            img.dataset.name,
            img.dataset.size
        );
        if (html) img.outerHTML = html;
    }
}

window.__gmsProductImgError = handleProductImageError;
