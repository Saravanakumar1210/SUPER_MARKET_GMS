const filterState = {
    selectedCategories: [],
    selectedSubCategories: [],
    selectedCultures: [],
    searchQuery: '',
    sortBy: 'none',
    currentPage: 1,
    perPage: 96,
    spotlightSection: null
};

const SPOTLIGHT_FILTERS = [
    { key: 'featured', label: 'Featured products', icon: 'fa-star', getter: () => getFeaturedProducts() },
    { key: 'bestSellers', label: 'Best Sellers', icon: 'fa-ranking-star', getter: () => getBestSellerProducts() },
    { key: 'newArrivals', label: 'New Arrivals', icon: 'fa-wand-magic-sparkles', getter: () => getNewArrivalProducts() },
    { key: 'hotOffers', label: 'Hot Offers', icon: 'fa-fire', getter: () => getHotOfferProducts() },
    { key: 'exclusive', label: 'Exclusive products', icon: 'fa-gem', getter: () => getExclusiveProducts() }
];

let cachedFilterHash = '';
let cachedFilteredProducts = [];
let cachedTotalCount = 0;

function getFilterHash() {
    return JSON.stringify({
        selectedCategories: filterState.selectedCategories,
        selectedSubCategories: filterState.selectedSubCategories,
        selectedCultures: filterState.selectedCultures,
        searchQuery: filterState.searchQuery,
        sortBy: filterState.sortBy,
        spotlightSection: filterState.spotlightSection
    });
}

function shuffleProducts(products) {
    const shuffled = [...products];
    for (let i = shuffled.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
}

function sortProducts(products) {
    const sorted = [...products];
    if (filterState.spotlightSection && filterState.sortBy === 'none') {
        sorted.sort((a, b) => a.displayName.localeCompare(b.displayName));
        return sorted;
    }
    switch (filterState.sortBy) {
        case 'name-asc':
            sorted.sort((a, b) => a.displayName.localeCompare(b.displayName));
            break;
        case 'name-desc':
            sorted.sort((a, b) => b.displayName.localeCompare(a.displayName));
            break;
        case 'none':
        default:
            return shuffleProducts(sorted);
    }
    return sorted;
}

function applyFilters(skipPageReset) {
    const hash = getFilterHash();

    if (hash !== cachedFilterHash) {
        let results = ALL_PRODUCTS;

        if (filterState.spotlightSection) {
            const spotlight = SPOTLIGHT_FILTERS.find(s => s.key === filterState.spotlightSection);
            results = spotlight ? spotlight.getter() : [];
        } else if (filterState.selectedCultures.length > 0) {
            results = typeof getProductsForCultures === 'function'
                ? getProductsForCultures(filterState.selectedCultures)
                : [];
            if (filterState.selectedCategories.length > 0) {
                results = results.filter(p =>
                    filterState.selectedCategories.includes(p.categoryName)
                );
            }
            if (filterState.selectedSubCategories.length > 0) {
                results = results.filter(p =>
                    filterState.selectedSubCategories.includes(p.subCategoryName)
                );
            }
        } else {
            if (filterState.selectedCategories.length > 0) {
                results = results.filter(p =>
                    filterState.selectedCategories.includes(p.categoryName)
                );
            }

            if (filterState.selectedSubCategories.length > 0) {
                results = results.filter(p =>
                    filterState.selectedSubCategories.includes(p.subCategoryName)
                );
            }
        }

        if (filterState.searchQuery.trim()) {
            const query = filterState.searchQuery.trim().toLowerCase();
            results = results.filter(p =>
                p.displayName.toLowerCase().includes(query) ||
                p.productName.toLowerCase().includes(query)
            );
        }

        cachedFilteredProducts = sortProducts(results);
        cachedTotalCount = cachedFilteredProducts.length;
        cachedFilterHash = hash;

        if (!skipPageReset) {
            filterState.currentPage = 1;
        }
    }

    const totalPages = Math.max(1, Math.ceil(cachedTotalCount / filterState.perPage));
    if (filterState.currentPage > totalPages) {
        filterState.currentPage = totalPages;
    }

    const start = (filterState.currentPage - 1) * filterState.perPage;
    const pageProducts = cachedFilteredProducts.slice(start, start + filterState.perPage);

    if (typeof renderGrid === 'function') {
        renderGrid(pageProducts, cachedTotalCount);
    }
    if (typeof renderPagination === 'function') {
        renderPagination(cachedTotalCount);
    }
    if (typeof updateResultCount === 'function') {
        updateResultCount(pageProducts.length, cachedTotalCount);
    }
    if (typeof renderActiveFilterChips === 'function') {
        renderActiveFilterChips();
    }
    if (typeof updateFilterSidebarMeta === 'function') {
        updateFilterSidebarMeta();
    }
    if (typeof renderCategoryPageHeader === 'function') {
        renderCategoryPageHeader();
    }
    if (typeof onFiltersApplied === 'function') {
        onFiltersApplied();
    }

    return { products: pageProducts, total: cachedTotalCount };
}

function clearAllFilters() {
    filterState.selectedCategories = [];
    filterState.selectedSubCategories = [];
    filterState.selectedCultures = [];
    filterState.searchQuery = '';
    filterState.sortBy = 'none';
    filterState.currentPage = 1;
    filterState.spotlightSection = null;
    cachedFilterHash = '';

    const searchInput = document.getElementById('header-search');
    if (searchInput) searchInput.value = '';

    const sortSelect = document.getElementById('sort-select');
    if (sortSelect) sortSelect.value = 'none';

    collapseAllCategoryBlocks();
    document.querySelectorAll('.filter-checkbox').forEach(cb => { cb.checked = false; });
    syncCultureCheckboxes();
    syncSpotlightFilterUI();
    applyFilters();
}

function setSubCategoryFilter(subCategoryName, checked, sourceCheckbox) {
    if (checked) {
        filterState.spotlightSection = null;
        if (!filterState.selectedSubCategories.includes(subCategoryName)) {
            filterState.selectedSubCategories.push(subCategoryName);
        }
    } else {
        filterState.selectedSubCategories = filterState.selectedSubCategories.filter(s => s !== subCategoryName);
    }
    cachedFilterHash = '';
    syncSubcategoryCheckboxes(subCategoryName, checked, sourceCheckbox);
    syncSpotlightFilterUI();
    applyFilters();
}

function syncSubcategoryCheckboxes(subCategoryName, checked, sourceCheckbox) {
    document.querySelectorAll(`[data-filter-subcategory="${CSS.escape(subCategoryName)}"]`).forEach(cb => {
        if (cb !== sourceCheckbox) cb.checked = checked;
    });
}

function syncCategoryCheckboxes(categoryName, checked, sourceCheckbox) {
    document.querySelectorAll(`[data-filter-category="${CSS.escape(categoryName)}"]`).forEach(cb => {
        if (cb !== sourceCheckbox) cb.checked = checked;
    });
}

function setCultureFilter(cultureKey, checked, sourceCheckbox) {
    if (checked) {
        filterState.spotlightSection = null;
        if (!filterState.selectedCultures.includes(cultureKey)) {
            filterState.selectedCultures.push(cultureKey);
        }
    } else {
        filterState.selectedCultures = filterState.selectedCultures.filter(c => c !== cultureKey);
    }
    cachedFilterHash = '';
    syncCultureCheckboxes(cultureKey, checked, sourceCheckbox);
    syncSpotlightFilterUI();
    applyFilters();
}

function syncCultureCheckboxes(cultureKey, checked, sourceCheckbox) {
    if (cultureKey === undefined) {
        document.querySelectorAll('[data-filter-culture]').forEach(cb => {
            cb.checked = filterState.selectedCultures.includes(cb.dataset.filterCulture);
        });
        return;
    }
    document.querySelectorAll(`[data-filter-culture="${CSS.escape(cultureKey)}"]`).forEach(cb => {
        if (cb !== sourceCheckbox) cb.checked = checked;
    });
}

function setCategoryFilter(categoryName, checked, sourceCheckbox) {
    if (checked) {
        filterState.spotlightSection = null;
        if (!filterState.selectedCategories.includes(categoryName)) {
            filterState.selectedCategories.push(categoryName);
        }
    } else {
        filterState.selectedCategories = filterState.selectedCategories.filter(c => c !== categoryName);
        const subsInCategory = getSubcategoriesForCategory(categoryName).map(s => s.SubCategoryName);
        filterState.selectedSubCategories = filterState.selectedSubCategories.filter(
            s => !subsInCategory.includes(s)
        );
        collapseCategoryBlock(categoryName);
    }
    cachedFilterHash = '';
    syncCategoryCheckboxes(categoryName, checked, sourceCheckbox);
    syncSpotlightFilterUI();
    applyFilters();
}

function collapseCategoryBlock(categoryName) {
    document.querySelectorAll(`.filter-category-block[data-category="${CSS.escape(categoryName)}"]`).forEach(block => {
        block.classList.remove('is-open');
        const trigger = block.querySelector('.filter-cat-trigger');
        if (trigger) trigger.setAttribute('aria-expanded', 'false');
        const panel = block.querySelector('.filter-sub-panel');
        if (panel) panel.setAttribute('aria-hidden', 'true');
    });
}

function collapseAllCategoryBlocks() {
    document.querySelectorAll('.filter-category-block').forEach(block => {
        block.classList.remove('is-open');
        const trigger = block.querySelector('.filter-cat-trigger');
        if (trigger) trigger.setAttribute('aria-expanded', 'false');
        const panel = block.querySelector('.filter-sub-panel');
        if (panel) panel.setAttribute('aria-hidden', 'true');
    });
}

function toggleCategoryBlock(block, open) {
    const categoryName = block.dataset.category;
    document.querySelectorAll(`.filter-category-block[data-category="${CSS.escape(categoryName)}"]`).forEach(mirror => {
        mirror.classList.toggle('is-open', open);
        const trigger = mirror.querySelector('.filter-cat-trigger');
        if (trigger) trigger.setAttribute('aria-expanded', String(open));
        const panel = mirror.querySelector('.filter-sub-panel');
        if (panel) panel.setAttribute('aria-hidden', String(!open));
    });
}

function openCategoryBlocksFromState() {
    filterState.selectedCategories.forEach(catName => {
        const block = document.querySelector(`.filter-category-block[data-category="${CSS.escape(catName)}"]`);
        if (block) toggleCategoryBlock(block, true);
    });
}

function bindCategoryFilterEvents(root = document) {
    const categoryList = root === document
        ? document.getElementById('category-filter-list')
        : root.querySelector('#category-filter-list');
    if (!categoryList || categoryList.dataset.filterBound) return;
    categoryList.dataset.filterBound = '1';

    categoryList.addEventListener('change', (e) => {
        const cb = e.target;
        if (!cb.matches('.stamp-check')) return;
        if (cb.dataset.filterCategory) {
            e.stopPropagation();
            setCategoryFilter(cb.dataset.filterCategory, cb.checked, cb);
        } else if (cb.dataset.filterSubcategory) {
            setSubCategoryFilter(cb.dataset.filterSubcategory, cb.checked, cb);
        }
    });

    categoryList.addEventListener('click', (e) => {
        if (e.target.closest('.stamp-check')) return;
        const trigger = e.target.closest('.filter-cat-trigger');
        if (!trigger) return;
        const block = trigger.closest('.filter-category-block');
        if (!block) return;
        const open = !block.classList.contains('is-open');
        toggleCategoryBlock(block, open);
    });
}

function removeFilterChip(type, value) {
    if (type === 'category') {
        filterState.selectedCategories = filterState.selectedCategories.filter(c => c !== value);
        const subsInCategory = getSubcategoriesForCategory(value).map(s => s.SubCategoryName);
        filterState.selectedSubCategories = filterState.selectedSubCategories.filter(
            s => !subsInCategory.includes(s)
        );
        collapseCategoryBlock(value);
        syncCategoryCheckboxes(value, false);
    } else if (type === 'subcategory') {
        filterState.selectedSubCategories = filterState.selectedSubCategories.filter(s => s !== value);
        syncSubcategoryCheckboxes(value, false);
    } else if (type === 'culture') {
        filterState.selectedCultures = filterState.selectedCultures.filter(c => c !== value);
        syncCultureCheckboxes(value, false);
    } else if (type === 'search') {
        filterState.searchQuery = '';
        const searchInput = document.getElementById('header-search');
        if (searchInput) searchInput.value = '';
    } else if (type === 'spotlight') {
        filterState.spotlightSection = null;
        syncSpotlightFilterUI();
    }
    cachedFilterHash = '';
    applyFilters();
}

function renderCultureFilterList() {
    const cultureList = document.getElementById('culture-filter-list');
    if (!cultureList || !KITCHEN_CULTURE_DEFS.length) return;

    const chevSvg = '<svg class="filter-cat-chev filter-culture-chev" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>';

    cultureList.innerHTML = KITCHEN_CULTURE_DEFS.map(culture => {
        const isSelected = filterState.selectedCultures.includes(culture.key);
        return `
            <div class="filter-category-block filter-culture-block" data-culture="${culture.key}">
                <div class="filter-cat-row">
                    <span class="filter-cat-check-wrap">
                        <input type="checkbox" class="stamp-check filter-checkbox"
                            data-filter-culture="${culture.key}"
                            ${isSelected ? 'checked' : ''}
                            aria-label="Filter by ${culture.label}">
                    </span>
                    <button type="button" class="filter-cat-trigger is-close" aria-expanded="false">
                        <span class="filter-cat-name">${culture.label}</span>
                        ${chevSvg}
                    </button>
                </div>
            </div>`;
    }).join('');
}

function bindCultureFilterEvents(root = document) {
    const cultureList = root === document
        ? document.getElementById('culture-filter-list')
        : root.querySelector('#culture-filter-list');
    if (!cultureList || cultureList.dataset.filterBound) return;
    cultureList.dataset.filterBound = '1';

    cultureList.addEventListener('change', (e) => {
        const cb = e.target;
        if (!cb.matches('.stamp-check') || !cb.dataset.filterCulture) return;
        e.stopPropagation();
        setCultureFilter(cb.dataset.filterCulture, cb.checked, cb);
    });

    cultureList.addEventListener('click', (e) => {
        if (e.target.closest('.stamp-check')) return;
        const trigger = e.target.closest('.filter-cat-trigger');
        if (!trigger) return;
        const block = trigger.closest('.filter-culture-block');
        if (!block) return;
        const cb = block.querySelector('[data-filter-culture]');
        if (cb) {
            cb.checked = !cb.checked;
            setCultureFilter(cb.dataset.filterCulture, cb.checked, cb);
        }
    });
}

function renderCategoryFilterList() {
    const categoryList = document.getElementById('category-filter-list');
    if (!categoryList) return;

    const chevSvg = '<svg class="filter-cat-chev" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>';
    const stats = getCategoryStats();

    categoryList.innerHTML = stats.map(cat => {
        const isSelected = filterState.selectedCategories.includes(cat.CategoryName);
        const subs = getSubcategoriesForCategory(cat.CategoryName);
        const subsHtml = subs.map(sub => `
            <label class="filter-sub-row">
                <input type="checkbox" class="stamp-check filter-checkbox"
                    data-filter-subcategory="${sub.SubCategoryName}"
                    ${filterState.selectedSubCategories.includes(sub.SubCategoryName) ? 'checked' : ''}>
                <span class="filter-sub-label">${normalizeCategoryName(sub.SubCategoryName)}</span>
            </label>
        `).join('');

        return `
            <div class="filter-category-block" data-category="${cat.CategoryName}">
                <div class="filter-cat-row">
                    <span class="filter-cat-check-wrap">
                        <input type="checkbox" class="stamp-check filter-checkbox"
                            data-filter-category="${cat.CategoryName}"
                            ${isSelected ? 'checked' : ''}
                            aria-label="Filter by ${normalizeCategoryName(cat.CategoryName)}">
                    </span>
                    <button type="button" class="filter-cat-trigger" aria-expanded="false">
                        <span class="filter-cat-name">${normalizeCategoryName(cat.CategoryName)}</span>
                        ${chevSvg}
                    </button>
                </div>
                ${subs.length ? `
                <div class="filter-sub-panel" aria-hidden="true">
                    <div>
                        <div class="filter-sub-list" role="group"
                            aria-label="Subcategories for ${normalizeCategoryName(cat.CategoryName)}">
                            ${subsHtml}
                        </div>
                    </div>
                </div>` : ''}
            </div>
        `;
    }).join('');
}

function updateFilterSidebarMeta() {
    const activeCount = filterState.selectedCategories.length
        + filterState.selectedSubCategories.length
        + filterState.selectedCultures.length
        + (filterState.searchQuery.trim() ? 1 : 0)
        + (filterState.spotlightSection ? 1 : 0);

    document.querySelectorAll('.js-filter-active-count').forEach(el => {
        el.textContent = activeCount;
    });
}

function renderActiveFilterChips() {
    const containers = document.querySelectorAll('#active-filter-chips, .filter-panel-chips');
    if (!containers.length) return;

    const chips = [];

    filterState.selectedCultures.forEach(key => {
        chips.push({
            type: 'culture',
            label: typeof getCultureLabel === 'function' ? getCultureLabel(key) : key,
            value: key,
        });
    });
    filterState.selectedCategories.forEach(cat => {
        chips.push({ type: 'category', label: normalizeCategoryName(cat), value: cat });
    });
    filterState.selectedSubCategories.forEach(sub => {
        chips.push({ type: 'subcategory', label: normalizeCategoryName(sub), value: sub });
    });
    if (filterState.searchQuery.trim()) {
        chips.push({ type: 'search', label: `"${filterState.searchQuery}"`, value: filterState.searchQuery });
    }
    if (filterState.spotlightSection) {
        const spotlight = SPOTLIGHT_FILTERS.find(s => s.key === filterState.spotlightSection);
        if (spotlight) {
            chips.push({ type: 'spotlight', label: spotlight.label, value: spotlight.key });
        }
    }

    const chipsHtml = chips.map(chip => `
        <button type="button" class="filter-panel-chip" data-chip-type="${chip.type}" data-chip-value="${chip.value}"
            aria-label="Remove ${chip.label} filter">
            ${chip.label}
            <span class="filter-panel-chip-x" aria-hidden="true">&times;</span>
        </button>
    `).join('');

    containers.forEach(container => {
        container.innerHTML = chipsHtml;
        container.querySelectorAll('.filter-panel-chip').forEach(btn => {
            btn.addEventListener('click', () => {
                removeFilterChip(btn.dataset.chipType, btn.dataset.chipValue);
            });
        });
    });
}

function setSpotlightFilter(sectionKey) {
    filterState.spotlightSection = sectionKey;
    if (sectionKey) {
        filterState.selectedCategories = [];
        filterState.selectedSubCategories = [];
        filterState.selectedCultures = [];
        collapseAllCategoryBlocks();
        document.querySelectorAll('.filter-checkbox').forEach(cb => { cb.checked = false; });
        syncCultureCheckboxes();
    }
    cachedFilterHash = '';
    syncSpotlightFilterUI();
    applyFilters();
}

function syncSpotlightFilterUI() {
    document.querySelectorAll('.filter-spotlight-btn').forEach(btn => {
        const active = btn.dataset.spotlight === filterState.spotlightSection;
        btn.classList.toggle('is-active', active);
        btn.setAttribute('aria-pressed', String(active));
    });
}

function renderSpotlightFilterSections() {
    const container = document.getElementById('spotlight-filter-sections');
    if (!container) return;

    container.innerHTML = SPOTLIGHT_FILTERS.map(section => {
        const active = filterState.spotlightSection === section.key;
        return `
            <section class="filter-panel-group">
                <button type="button"
                    class="filter-acc-trigger filter-spotlight-btn${active ? ' is-active' : ''}"
                    data-spotlight="${section.key}"
                    aria-pressed="${active}">
                    <span class="filter-acc-label">
                        <span class="filter-stub-dot" aria-hidden="true"></span>
                        <span class="filter-acc-title">${section.label}</span>
                    </span>
                </button>
            </section>`;
    }).join('');
}

function bindSpotlightFilterEvents(root = document) {
    const container = root === document
        ? document.getElementById('spotlight-filter-sections')
        : root.querySelector('#spotlight-filter-sections');
    if (!container || container.dataset.spotlightBound) return;
    container.dataset.spotlightBound = '1';

    container.addEventListener('click', (e) => {
        const btn = e.target.closest('.filter-spotlight-btn');
        if (!btn) return;
        const key = btn.dataset.spotlight;
        setSpotlightFilter(filterState.spotlightSection === key ? null : key);
    });
}

function buildSidebarFilters() {
    renderSpotlightFilterSections();
    renderCultureFilterList();
    renderCategoryFilterList();
    openCategoryBlocksFromState();
    bindCultureFilterEvents();
    bindCategoryFilterEvents();
    bindSpotlightFilterEvents();
    initFilterAccordions();
    initClearAllButton();
}

function initFilterAccordions(root = document) {
    const scope = root === document ? document : root;
    scope.querySelectorAll('.filter-acc-trigger:not(.filter-spotlight-btn)').forEach(trigger => {
        if (trigger.dataset.accBound) return;
        trigger.dataset.accBound = '1';
        trigger.addEventListener('click', () => {
            const open = trigger.classList.toggle('is-open');
            trigger.setAttribute('aria-expanded', String(open));
            const panel = trigger.nextElementSibling;
            if (panel?.classList.contains('filter-acc-panel')) {
                panel.classList.toggle('is-open', open);
            }
        });
    });
}

function initClearAllButton(root = document) {
    const scope = root === document ? document : root;
    scope.querySelectorAll('#clear-all-filters, .filter-panel-clear').forEach(btn => {
        if (btn.dataset.clearBound) return;
        btn.dataset.clearBound = '1';
        btn.addEventListener('click', clearAllFilters);
    });
}

function initSortControl() {
    const sortSelect = document.getElementById('sort-select');
    if (!sortSelect) return;
    // Reflect current state (e.g. set via URL param)
    sortSelect.value = filterState.sortBy;
    sortSelect.addEventListener('change', () => {
        filterState.sortBy = sortSelect.value;
        cachedFilterHash = '';
        pushFilterState();
        applyFilters(true);
    });
}

function initPerPageControl() {
    const perPageSelect = document.getElementById('per-page-select');
    if (!perPageSelect) return;
    perPageSelect.value = filterState.perPage;
    perPageSelect.addEventListener('change', () => {
        filterState.perPage = parseInt(perPageSelect.value, 10);
        filterState.currentPage = 1;
        cachedFilterHash = '';
        pushFilterState();
        applyFilters();
    });
}

function initViewToggle() {
    const gridBtn = document.getElementById('view-grid');
    const listBtn = document.getElementById('view-list');
    const grid = document.getElementById('product-grid');

    if (!gridBtn || !listBtn || !grid) return;

    gridBtn.addEventListener('click', () => {
        grid.classList.remove('list-view');
        gridBtn.classList.add('active');
        listBtn.classList.remove('active');
    });
    listBtn.addEventListener('click', () => {
        grid.classList.add('list-view');
        listBtn.classList.add('active');
        gridBtn.classList.remove('active');
    });
}

function applyUrlParams() {
    const params = new URLSearchParams(window.location.search);
    const category = params.get('category');
    const subcategory = params.get('subcategory');
    const search = params.get('search');
    const sort = params.get('sort');
    const perPage = params.get('perPage');

    if (category) {
        const match = findCategoryByParam(category);
        if (match) {
            filterState.selectedCategories = [match.CategoryName];
        }
    }
    if (subcategory) {
        const match = findSubcategoryByParam(subcategory);
        if (match) {
            filterState.selectedSubCategories = [match.SubCategoryName];
            if (filterState.selectedCategories.length === 0) {
                filterState.selectedCategories = [match.CategoryName];
            }
        }
    }
    if (search) {
        filterState.searchQuery = search;
        const searchInput = document.getElementById('header-search');
        if (searchInput) searchInput.value = search;
    }
    if (sort) {
        const sortMap = {
            'none': 'none',
            'name-asc': 'name-asc',
            'name-desc': 'name-desc'
        };
        if (sortMap[sort]) {
            filterState.sortBy = sortMap[sort];
            const sortSelect = document.getElementById('sort-select');
            if (sortSelect) sortSelect.value = sortMap[sort];
        }
    }
    if (perPage) {
        const parsed = parseInt(perPage, 10);
        if ([24, 48, 96, 192].includes(parsed)) {
            filterState.perPage = parsed;
            const perPageSelect = document.getElementById('per-page-select');
            if (perPageSelect) perPageSelect.value = parsed;
        }
    }
    const section = params.get('section');
    if (section && SPOTLIGHT_FILTERS.some(s => s.key === section)) {
        filterState.spotlightSection = section;
    }
    const culture = params.get('culture');
    if (culture) {
        const keys = culture.split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
        const valid = keys.filter(k => KITCHEN_CULTURE_DEFS.some(c => c.key === k));
        if (valid.length) filterState.selectedCultures = valid;
    }
}

/**
 * Push current filter preferences into the URL so refresh/share keeps state.
 */
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
    const newUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
    history.replaceState(null, '', newUrl);
}
