function renderAboutTeaserStats() {
    const stats = getCategoryStats();
    const elProducts = document.getElementById('teaser-products');
    const elCategories = document.getElementById('teaser-categories');
    const elLocations = document.getElementById('teaser-locations');

    if (elProducts) elProducts.textContent = getTotalProductCount().toLocaleString();
    if (elCategories) elCategories.textContent = stats.length.toLocaleString();
    if (elLocations) elLocations.textContent = uniqueLocationIds.length.toLocaleString();
}

function renderAboutCategories() {
    const list = document.getElementById('about-category-list');
    if (!list) return;

    const cats = getCategoryStats();
    const subs = getSubcategoryStats();

    // Group subcategories by parent
    const subsByParent = {};
    subs.forEach(s => {
        if (!subsByParent[s.ProductCategoryID]) subsByParent[s.ProductCategoryID] = [];
        subsByParent[s.ProductCategoryID].push(s);
    });

    list.innerHTML = cats.map(cat => {
        const catSubs = subsByParent[cat.ProductCategoryID] || [];
        const placeholder = getCategoryPlaceholder(cat.CategoryName);
        const subTags = catSubs.map(s =>
            `<a href="products.html?category=${encodeURIComponent(cat.CategoryName)}&subcategory=${encodeURIComponent(s.SubCategoryName)}" class="about-sub-tag">${s.SubCategoryName} <span>${s.Product_Count}</span></a>`
        ).join('');
        return `
            <li class="about-cat-item">
                <div class="about-cat-header">
                    <span class="about-cat-icon" style="background:${placeholder.gradient}">
                        <i class="fa-solid ${placeholder.icon}"></i>
                    </span>
                    <a href="products.html?category=${encodeURIComponent(cat.CategoryName)}" class="about-cat-name">${cat.CategoryName}</a>
                    <span class="about-cat-count">${cat.Product_Count.toLocaleString()} products</span>
                </div>
                ${subTags ? `<div class="about-sub-tags">${subTags}</div>` : ''}
            </li>
        `;
    }).join('');
}

function renderFooterCategories() {
    const container = document.getElementById('footer-cat-list');
    if (!container) return;
    const stats = getCategoryStats().slice(0, 7);
    container.innerHTML = stats.map(cat => `
        <a href="products.html?category=${encodeURIComponent(cat.CategoryName)}">
            ${normalizeCategoryName(cat.CategoryName)}
            <span class="fcat-count">${cat.Product_Count}</span>
        </a>
    `).join('');
}

function initHomePage() {
    if (typeof resetHomePageScroll === 'function') resetHomePageScroll();
    if (typeof refreshHeroSlider === 'function') refreshHeroSlider();
    if (typeof renderTopCategories === 'function') renderTopCategories();
    if (typeof initTopCatCarousel === 'function') initTopCatCarousel();
    if (ALL_PRODUCTS.length && typeof renderFeaturedProducts === 'function') {
        renderFeaturedProducts();
    } else if (typeof renderHomeProductSkeletons === 'function') {
        renderHomeProductSkeletons();
    }
    if (typeof renderTestimonials === 'function') renderTestimonials();
    renderAboutTeaserStats();
    renderFooterCategories();
}

function setStoreDataLoading(isLoading) {
    document.body.classList.toggle('gms-data-loading', Boolean(isLoading));
}

// Category descriptions for the page header — keyed on the actual CategoryName from data
const CATEGORY_DESCRIPTIONS = {
    'Dry grocery & staples':
        'Rice, lentils, spices, masalas, atta, cooking oils, ghee, nuts, dry fruits and everyday pantry essentials — the backbone of any world-foods kitchen.',
    'Snacks & confectionery':
        'Namkeen, biscuits, chocolates, Indian mithai, crisps and savoury snacks from trusted brands across South Asia, the UK and beyond.',
    'Beverages':
        'Tea, coffee, soft drinks, fruit juices, malt drinks, health drinks, cordials and water — a full drinks range for every occasion.',
    'Fresh produce':
        'Root vegetables, onions, leafy greens, herbs, gourds, pods and exotic specialty produce sourced fresh and restocked daily.',
    'Frozen, meat & ready-to-cook':
        'Frozen meat, poultry, fish, seafood and ready-to-cook marinated products — convenient and quality assured.',
    'Condiments, sauces & pickles':
        'Pickles, chutneys, cooking sauces, ketchup, pastes, purees, honey, jams, spreads and vinegar from world cuisine traditions.',
    'Dairy, eggs & chilled':
        'Milk powder, condensed milk, cheese, fresh dairy and eggs — refrigerated essentials for home and trade customers.',
    'Household & personal care':
        'Personal care, toiletries, hair care, skin care, cosmetics, household cleaning, laundry, disposables, packaging and health products.',
    'Bakery, pasta & noodles':
        'Bread, bakery items, noodles, instant meals, pasta, macaroni, breakfast cereals, oats and canned & tinned foods.',
    // Subcategory descriptions
    'Rice & rice products':
        'Basmati, jasmine, long-grain, broken and specialty rice varieties — wholesale and retail packs.',
    'Lentils, dal & pulses':
        'Red lentils, toor dal, chana, moong, urad and a full range of pulses for everyday cooking.',
    'Spices & masalas':
        'Ground spices, blended masalas, curry powders and seasoning mixes from leading brands including MDH, Rajah, TRS and Natco.',
    'Atta, flour & semolina':
        'Chapatti flour, plain and self-raising flour, semolina, cornmeal and specialty grains.',
    'Whole spices & herbs':
        'Cardamom, cloves, cinnamon, cumin, coriander seeds, bay leaves and dried herbs.',
    'Cooking oil & ghee':
        'Sunflower oil, vegetable oil, mustard oil, coconut oil and ghee in a range of sizes.',
    'Nuts, dry fruits & seeds':
        'Almonds, cashews, pistachios, walnuts, raisins, dates, figs and mixed dry fruits.',
    'Sugar, jaggery & sweeteners':
        'White sugar, brown sugar, jaggery, coconut sugar and natural sweeteners.',
    'Salt, vinegar & baking basics':
        'Table salt, rock salt, malt vinegar, baking powder, bicarbonate of soda and yeast.',
    'Snacks & namkeen':
        'Chanachur, chevda, sev, bhujia, mixture and Indian savoury snack assortments.',
    'Biscuits & cookies':
        'Digestives, cream biscuits, Marie biscuits, bourbon, shortbread and specialty cookies.',
    'Chocolates & candy':
        'Milk chocolate, dark chocolate, candy bars and sweets from international brands.',
    'Sweets & Indian mithai':
        'Ladoo, barfi, halwa, rasgulla, gulab jamun and traditional Indian sweets.',
    'Crisps & savoury snacks':
        'Potato crisps, puffs, corn snacks and flavoured savoury bites.',
    'Tea & herbal tea':
        'PG Tips, Tetley, Lipton, masala chai, green tea and herbal infusions.',
    'Coffee & instant coffee':
        'Ground coffee, instant coffee, espresso and coffee mixes from popular brands.',
    'Soft drinks & fizzy drinks':
        'Colas, lemonade, energy drinks and international fizzy drink brands.',
    'Fruit juices & nectars':
        'Mango juice, guava nectar, mixed fruit and tropical juice drinks.',
    'Malt drinks & health drinks':
        'Horlicks, Ovaltine, Complan, Bournvita and nourishing malt beverages.',
    'Syrups, concentrates & cordials':
        'Rose syrup, rooh afza, fruit cordials and concentrated drinks.',
    'Water & coconut water':
        'Still and sparkling water, coconut water and natural hydration drinks.',
    'Root vegetables & onions':
        'Potatoes, carrots, sweet potatoes, onions, garlic, ginger and root vegetables.',
    'Leafy greens & herbs':
        'Spinach, methi, curry leaves, coriander, mint and seasonal leafy greens.',
    'Gourds, pods & vegetables':
        'Bitter gourd, ridge gourd, okra, drumstick, aubergine, courgette and tropical vegetables.',
    'Exotic & specialty vegetables':
        'Taro, lotus root, raw banana, jackfruit, yam and hard-to-find specialty produce.',
    'Frozen meat & poultry':
        'Halal chicken, lamb, mutton and mixed meat cuts — individually frozen and bulk packs.',
    'Frozen fish & seafood':
        'Tilapia, catfish, prawns, shrimp, kingfish and seafood assortments.',
    'Ready-to-cook & marinated':
        'Marinated chicken, kebab mixes and pre-seasoned ready-to-cook convenience products.',
    'Pickles & chutneys':
        'Mango pickle, lime pickle, mixed vegetable pickle and chutneys from Patak\'s, Ahmed and more.',
    'Sauces, ketchup & cooking sauces':
        'Tomato ketchup, hot sauce, soy sauce, oyster sauce and curry cooking sauces.',
    'Cooking pastes & purees':
        'Garlic paste, ginger paste, tamarind paste, tomato puree and blended cooking bases.',
    'Honey, jam & spreads':
        'Pure honey, fruit jams, peanut butter and breakfast spreads.',
    'Vinegar & cooking essentials':
        'Malt vinegar, white vinegar, cooking wine and fermentation essentials.',
    'Milk powder & condensed milk':
        'Full-cream milk powder, skimmed milk powder and sweetened condensed milk.',
    'Cheese & dairy products':
        'Block cheese, processed cheese, cream cheese and butter.',
    'Eggs':
        'Fresh free-range and barn eggs in medium, large and extra-large sizes.',
    'Personal care & toiletries':
        'Soap, shower gel, shampoo, deodorant and daily personal care essentials.',
    'Hair care products':
        'Hair oil, shampoo, conditioner, hair dye and styling products.',
    'Skin care & cosmetics':
        'Moisturisers, face wash, fairness cream and cosmetic essentials.',
    'Household cleaning':
        'Bleach, disinfectant, multi-surface cleaner and floor cleaning products.',
    'Laundry products':
        'Washing powder, liquid detergent, fabric conditioner and stain remover.',
    'Disposables & packaging':
        'Carrier bags, food containers, cling film, foil and disposable tableware.',
    'Health & OTC medicines':
        'Paracetamol, vitamins, supplements and over-the-counter health products.',
    'Bread & bakery items':
        'Sliced bread, rolls, pitta, naan and specialty bakery products.',
    'Noodles & instant meals':
        'Instant noodles, rice noodles, pot noodles and quick-cook meal kits.',
    'Pasta & macaroni':
        'Spaghetti, penne, fusilli, macaroni and specialty pasta shapes.',
    'Breakfast cereals & oats':
        'Porridge oats, cornflakes, muesli and fortified breakfast cereals.',
    'Canned & tinned foods':
        'Canned tomatoes, chickpeas, kidney beans, sardines, tuna and tinned vegetables.',
    'DEFAULT': 'Browse our quality product range in this category, sourced from trusted suppliers around the world.'
};

function getCategoryDescription(name) {
    if (!name) return CATEGORY_DESCRIPTIONS.DEFAULT;
    // Exact match first
    if (CATEGORY_DESCRIPTIONS[name]) return CATEGORY_DESCRIPTIONS[name];
    // Case-insensitive fallback
    const lower = name.trim().toLowerCase();
    for (const [key, val] of Object.entries(CATEGORY_DESCRIPTIONS)) {
        if (key.toLowerCase() === lower) return val;
    }
    return CATEGORY_DESCRIPTIONS.DEFAULT;
}

function getCategoryForSubcategory(subCategoryName) {
    if (typeof getSubcategoryStats !== 'function') return null;
    const match = getSubcategoryStats().find(s => s.SubCategoryName === subCategoryName);
    return match ? match.CategoryName : null;
}

function getBreadcrumbSegments() {
    if (filterState.spotlightSection) {
        const spotlight = typeof SPOTLIGHT_FILTERS !== 'undefined'
            ? SPOTLIGHT_FILTERS.find(s => s.key === filterState.spotlightSection)
            : null;
        if (spotlight) return [spotlight.label];
    }

    const activeCultures = filterState.selectedCultures || [];
    if (activeCultures.length === 1 && !filterState.selectedCategories.length && !filterState.selectedSubCategories.length) {
        const label = typeof getCultureLabel === 'function'
            ? getCultureLabel(activeCultures[0])
            : activeCultures[0];
        return [label];
    }
    if (activeCultures.length > 1 && !filterState.selectedCategories.length && !filterState.selectedSubCategories.length) {
        return ['Cultures'];
    }

    const activeCats = filterState.selectedCategories;
    const activeSubs = filterState.selectedSubCategories || [];

    // Multiple categories → All products
    if (activeCats.length > 1) {
        return ['All products'];
    }

    // Multiple subcategories (same or different parent) → All products
    if (activeSubs.length > 1) {
        return ['All products'];
    }

    // Exactly one subcategory → Home › Products › Category › Subcategory
    if (activeSubs.length === 1) {
        const parentCat = getCategoryForSubcategory(activeSubs[0]);
        if (!parentCat) {
            return ['All products'];
        }
        if (activeCats.length === 1 && activeCats[0] !== parentCat) {
            return ['All products'];
        }
        return [
            normalizeCategoryName(parentCat),
            normalizeCategoryName(activeSubs[0])
        ];
    }

    // Single category only → Home › Products › Category
    if (activeCats.length === 1) {
        return [normalizeCategoryName(activeCats[0])];
    }

    // No filters → All products
    return ['All products'];
}

function renderCategoryPageHeader() {
    const nav = document.getElementById('cat-page-header');
    if (!nav) return;

    const segments = getBreadcrumbSegments();
    const sep = '<span class="breadcrumb-sep" aria-hidden="true"><i class="fa-solid fa-chevron-right"></i></span>';
    const esc = (s) => String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    let html = `<a href="index.html">Home</a>${sep}<a href="products.html">Products</a>`;

    segments.forEach((seg, i) => {
        html += sep;
        if (i === segments.length - 1) {
            html += `<span class="breadcrumb-current">${esc(seg)}</span>`;
        } else {
            html += `<span class="breadcrumb-current">${esc(seg)}</span>`;
        }
    });

    nav.innerHTML = html;
}

async function initProductsPage() {
    if (typeof renderSkeletonGrid === 'function') renderSkeletonGrid(12);
    if (typeof checkDataLoaded === 'function' && !checkDataLoaded()) return;

    if (typeof loadKitchenCultureDefs === 'function') {
        await loadKitchenCultureDefs();
    }
    applyUrlParams();
    buildSidebarFilters();
    initSortControl();
    initPerPageControl();
    initViewToggle();
    applyFilters();
    renderFooterCategories();
    renderRecentlyViewedOnPage();

    // Mobile filter drawer
    if (typeof initMobileFilterDrawer === 'function') initMobileFilterDrawer();
    // Sticky toolbar
    if (typeof initStickyToolbar === 'function') initStickyToolbar();
}

function renderRecentlyViewedOnPage() {
    if (typeof renderRecentlyViewed === 'function') {
        // slight delay so modal is available if user opens one immediately
        setTimeout(renderRecentlyViewed, 200);
    }
}

function initAboutPage() {
    renderAboutCategories();
    renderFooterCategories();
}

function bootBasketPage() {
    if (typeof GmsShoppingStore !== 'undefined') {
        GmsShoppingStore.hydrate(true);
    }

    initNavigation();
    initSearch();
    initModal();
    initScrollAnimations();

    document.addEventListener('gms:basket-updated', () => {
        if (typeof updateHeaderBadges === 'function') updateHeaderBadges();
        if (typeof GmsShoppingStore !== 'undefined') {
            document.querySelectorAll('.fp-card[data-product-name]').forEach(card => {
                if (typeof updateProductCardBasketState === 'function') {
                    updateProductCardBasketState(card.dataset.productName, card);
                }
            });
        }
    });

    document.addEventListener('gms:cart-updated', () => {
        if (typeof updateHeaderBadges === 'function') updateHeaderBadges();
    });

    if (typeof renderBasketPageEarly === 'function') renderBasketPageEarly();
    renderFooterCategories();

    if (typeof initBasketPage === 'function') initBasketPage();

    // Suggestions need the full catalog (same category/subcategory). Defer so the
    // basket UI paints first, then fill "You may also like / More from …".
    const loadRecs = () => {
        if (typeof whenCatalogReady !== 'function') return;
        whenCatalogReady()
            .then(() => {
                if (typeof onBasketCatalogReady === 'function') onBasketCatalogReady();
            })
            .catch(() => {});
    };
    if (typeof requestIdleCallback === 'function') {
        requestIdleCallback(loadRecs, { timeout: 1800 });
    } else {
        setTimeout(loadRecs, 150);
    }
}

function bootApp() {
    if (typeof GmsShoppingStore !== 'undefined') {
        GmsShoppingStore.hydrate(true);
    }

    initNavigation();
    if (typeof initSearch === 'function') initSearch();
    if (typeof initModal === 'function') initModal();
    initScrollAnimations();

    document.addEventListener('gms:basket-updated', () => {
        if (typeof updateHeaderBadges === 'function') updateHeaderBadges();
        if (typeof GmsShoppingStore !== 'undefined') {
            document.querySelectorAll('.fp-card[data-product-name]').forEach(card => {
                if (typeof updateProductCardBasketState === 'function') {
                    updateProductCardBasketState(card.dataset.productName, card);
                }
            });
        }
    });

    document.addEventListener('gms:cart-updated', () => {
        if (typeof updateHeaderBadges === 'function') updateHeaderBadges();
    });

    const page = document.body.dataset.page;

    switch (page) {
        case 'home':
            initHomePage();
            break;
        case 'products':
            initProductsPage();
            break;
        case 'about':
            initAboutPage();
            break;
        case 'contact':
            renderFooterCategories();
            break;
        case 'signup':
            if (typeof updateHeaderBadges === 'function') updateHeaderBadges();
            break;
        case 'account':
            if (typeof updateHeaderBadges === 'function') updateHeaderBadges();
            renderFooterCategories();
            break;
        default:
            if (typeof updateHeaderBadges === 'function') updateHeaderBadges();
            break;
    }
}

function initHomeCatalogOnSearch() {
    const input = document.getElementById('header-search');
    if (!input || typeof whenCatalogReady !== 'function') return;

    // Prefetch full catalog in the background so search is complete before typing
    whenCatalogReady().catch(() => {});

    const refreshIfTyping = () => {
        const dropdown = document.getElementById('search-dropdown');
        if (dropdown && input.value.trim() && typeof showSearchSuggestions === 'function') {
            showSearchSuggestions(input.value, dropdown, input);
        }
    };

    input.addEventListener('focus', () => {
        whenCatalogReady().then(refreshIfTyping).catch(() => {});
    });
    input.addEventListener('input', () => {
        if (typeof ALL_PRODUCTS !== 'undefined' && ALL_PRODUCTS.length < 200) {
            whenCatalogReady().then(refreshIfTyping).catch(() => {});
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    if (document.body.dataset.page === 'products' && typeof renderSkeletonGrid === 'function') {
        renderSkeletonGrid(12);
    }

    if (document.body.dataset.page === 'basket' || document.body.dataset.page === 'bucket') {
        if (typeof whenMetadataReady === 'function') {
            whenMetadataReady()
                .then(() => bootBasketPage())
                .catch(() => bootBasketPage());
        } else {
            bootBasketPage();
        }
        return;
    }

    if (document.body.dataset.page === 'home') {
        setStoreDataLoading(true);
        if (typeof renderHomeProductSkeletons === 'function') renderHomeProductSkeletons();
        if (typeof renderTopCategories === 'function') renderTopCategories();

        const bootHome = () => {
            bootApp();
            initHomeCatalogOnSearch();
            setStoreDataLoading(false);

            // Let the metadata-driven hero and categories paint before downloading
            // the small set of products used by the homepage strips.
            const loadProducts = () => {
                const productsReady = typeof whenHomeProductsReady === 'function'
                    ? whenHomeProductsReady()
                    : whenCatalogReady();

                productsReady
                    .then(() => {
                        if (typeof renderHomeProductStrips === 'function') renderHomeProductStrips();
                        renderAboutTeaserStats();
                    })
                    .catch(() => {
                        // Older servers may not have the optimized endpoint yet.
                        if (typeof whenCatalogReady !== 'function') return;
                        whenCatalogReady().then(() => {
                            if (typeof renderHomeProductStrips === 'function') renderHomeProductStrips();
                            renderAboutTeaserStats();
                        }).catch(() => {});
                    });
            };

            requestAnimationFrame(() => setTimeout(loadProducts, 0));
        };

        if (typeof whenMetadataReady === 'function') {
            whenMetadataReady()
                .then(bootHome)
                .catch(() => {
                    setStoreDataLoading(false);
                    bootHome();
                });
        } else {
            bootHome();
        }
        return;
    }

    const authOnlyPages = new Set(['signup', 'account']);
    if (authOnlyPages.has(document.body.dataset.page)) {
        if (typeof whenMetadataReady === 'function') {
            whenMetadataReady()
                .then(() => bootApp())
                .catch(() => bootApp());
        } else {
            bootApp();
        }
        return;
    }

    if (typeof whenCatalogReady !== 'function') {
        buildProductIndex();
        bootApp();
        return;
    }
    whenCatalogReady()
        .then(() => bootApp())
        .catch(() => {
            bootApp();
            if (typeof checkDataLoaded === 'function') checkDataLoaded();
        });
});
