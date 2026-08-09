'use strict';

/** @type {Record<string, string>} */
let SITE_SETTINGS = {};

function getSiteSettings() {
    return SITE_SETTINGS;
}

function digitsOnly(value) {
    return String(value || '').replace(/\D/g, '');
}

function phoneTelHref(phone) {
    let digits = digitsOnly(phone);
    if (!digits) return '#';
    // UK national numbers (leading 0) → E.164 with +44
    if (digits.startsWith('0') && !digits.startsWith('00')) {
        digits = `44${digits.slice(1)}`;
    }
    return `tel:+${digits}`;
}

function whatsAppUrl(number) {
    const digits = digitsOnly(number);
    return digits ? `https://wa.me/${digits}` : '#';
}

function fullStoreAddress(settings) {
    return [settings.store_address, settings.store_city, settings.store_postcode]
        .filter(Boolean)
        .join(', ');
}

function escapeSiteHtml(text) {
    return String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function renderParagraphsHtml(text) {
    return String(text || '')
        .split(/\n\s*\n/)
        .map(p => p.trim())
        .filter(Boolean)
        .map(p => `<p>${escapeSiteHtml(p)}</p>`)
        .join('');
}

function applySiteSettings(settings) {
    if (!settings || typeof settings !== 'object') return;
    SITE_SETTINGS = { ...settings };
    window.GMS_SITE_SETTINGS = SITE_SETTINGS;

    const phone = settings.store_phone || '';
    const waUrl = whatsAppUrl(settings.whatsapp_number);
    const addrFull = fullStoreAddress(settings);
    const promoAddress = [settings.store_address, settings.store_city].filter(Boolean).join(', ');

    document.querySelectorAll('.site-store-name').forEach(el => {
        if (settings.store_name) el.textContent = settings.store_name;
    });
    document.querySelectorAll('.site-store-tagline').forEach(el => {
        if (settings.store_tagline) el.textContent = settings.store_tagline;
    });
    document.querySelectorAll('.site-store-phone').forEach(el => {
        if (!phone) return;
        if (el.tagName === 'A') el.href = phoneTelHref(phone);
        el.textContent = phone;
    });
    document.querySelectorAll('.site-whatsapp-link').forEach(el => {
        if (waUrl !== '#') el.href = waUrl;
    });
    document.querySelectorAll('.site-footer-address').forEach(el => {
        if (addrFull) el.textContent = addrFull;
    });
    document.querySelectorAll('.site-footer-hours').forEach(el => {
        if (settings.opening_hours) el.textContent = settings.opening_hours;
    });
    document.querySelectorAll('.site-footer-desc').forEach(el => {
        if (settings.footer_desc) el.textContent = settings.footer_desc;
    });
    document.querySelectorAll('.site-promo-phone').forEach(el => {
        if (phone) el.textContent = `Call ${phone}`;
    });
    document.querySelectorAll('.site-promo-address').forEach(el => {
        if (promoAddress) el.textContent = promoAddress;
    });
    document.querySelectorAll('.site-delivery-area').forEach(el => {
        if (settings.delivery_area) el.textContent = settings.delivery_area;
    });
    document.querySelectorAll('.site-postcode-label').forEach(el => {
        if (settings.store_postcode) el.textContent = settings.store_postcode;
    });
    document.querySelectorAll('.site-city-label').forEach(el => {
        if (settings.store_city) el.textContent = settings.store_city;
    });

    const addrLine1 = document.getElementById('site-address-line1');
    const addrLine2 = document.getElementById('site-address-line2');
    const addrPostcode = document.getElementById('site-address-postcode');
    if (addrLine1 && settings.store_address) addrLine1.textContent = settings.store_address;
    if (addrLine2 && settings.store_city) addrLine2.textContent = settings.store_city;
    if (addrPostcode && settings.store_postcode) addrPostcode.textContent = settings.store_postcode;

    const hoursMonFri = document.getElementById('site-hours-mon-fri');
    const hoursSat = document.getElementById('site-hours-saturday');
    const hoursSun = document.getElementById('site-hours-sunday');
    if (hoursMonFri && settings.opening_hours_mon_fri) hoursMonFri.textContent = settings.opening_hours_mon_fri;
    if (hoursSat && settings.opening_hours_saturday) hoursSat.textContent = settings.opening_hours_saturday;
    if (hoursSun && settings.opening_hours_sunday) hoursSun.textContent = settings.opening_hours_sunday;

    const mapFrame = document.getElementById('site-map-iframe');
    if (mapFrame && settings.maps_embed_url) mapFrame.src = settings.maps_embed_url;

    const aboutIntro = document.getElementById('site-about-intro');
    if (aboutIntro && settings.about_us_text) {
        aboutIntro.innerHTML = renderParagraphsHtml(settings.about_us_text);
    }

    const homeTeaser = document.getElementById('site-home-about-teaser');
    if (homeTeaser) {
        const parts = [];
        if (settings.home_about_teaser) parts.push(`<p>${escapeSiteHtml(settings.home_about_teaser)}</p>`);
        if (settings.home_about_teaser_extra) parts.push(`<p>${escapeSiteHtml(settings.home_about_teaser_extra)}</p>`);
        if (parts.length) homeTeaser.innerHTML = parts.join('');
    }

    const email = settings.contact_email || '';
    document.querySelectorAll('.site-contact-email').forEach(el => {
        if (!email) return;
        if (el.tagName === 'A') el.href = `mailto:${email}`;
        el.textContent = email;
    });

    const socialWrap = document.getElementById('site-footer-social');
    if (socialWrap) {
        const links = [
            { key: 'social_facebook', icon: 'fa-brands fa-facebook-f', label: 'Facebook' },
            { key: 'social_instagram', icon: 'fa-brands fa-instagram', label: 'Instagram' },
            { key: 'social_twitter', icon: 'fa-brands fa-x-twitter', label: 'X' },
        ].filter(item => settings[item.key]);
        socialWrap.innerHTML = links.length
            ? links.map(item => `
                <a href="${escapeSiteHtml(settings[item.key])}" target="_blank" rel="noopener noreferrer" aria-label="${item.label}">
                    <i class="${item.icon}" aria-hidden="true"></i>
                </a>`).join('')
            : '';
        socialWrap.classList.toggle('hidden', links.length === 0);
    }

    applySiteAssetUrls(settings);
}

function applySiteAssetUrls(settings) {
    const logo = settings.store_logo_url;
    if (logo) {
        document.querySelectorAll('.logo-img, .adm-logo-img, .login-logo img').forEach(el => {
            el.src = logo;
        });
        // Keep dedicated small favicon assets in the browser tab — do not
        // replace them with a full-size store logo URL (often multi-MB).
    }

    if (settings.newsletter_background_url) {
        document.documentElement.style.setProperty(
            '--gms-newsletter-bg',
            `url('${settings.newsletter_background_url}')`
        );
    }

    if (settings.newsletter_visual_url) {
        document.querySelectorAll('.newsletter-banner__visual-img').forEach(el => {
            el.src = settings.newsletter_visual_url;
        });
    }

    if (settings.store_hero_image_url) {
        document.querySelectorAll('.page-hero--store').forEach(el => {
            el.style.backgroundImage = `url('${settings.store_hero_image_url}')`;
        });
    }

    let gallery = settings.store_gallery_urls;
    if (typeof gallery === 'string') {
        try { gallery = JSON.parse(gallery); } catch (_) { gallery = []; }
    }
    if (Array.isArray(gallery) && gallery.length) {
        document.querySelectorAll('.store-gallery__item img').forEach((img, i) => {
            if (gallery[i]) img.src = gallery[i];
        });
    }

    updateOpenNowBadge(settings);
    try {
        document.dispatchEvent(new CustomEvent('gms:site-settings', { detail: settings }));
    } catch (_) {}
}

/** Parse "8:00am – 9:00pm" (en/em dash) into [openMins, closeMins] from midnight. */
function parseHoursRangeToMinutes(rangeText) {
    const matches = String(rangeText || '').match(/(\d{1,2}):(\d{2})\s*(am|pm)/gi);
    if (!matches || matches.length < 2) return null;

    const toMins = (token) => {
        const m = token.match(/(\d{1,2}):(\d{2})\s*(am|pm)/i);
        if (!m) return null;
        let h = parseInt(m[1], 10);
        const mins = parseInt(m[2], 10);
        const ap = m[3].toLowerCase();
        if (ap === 'pm' && h !== 12) h += 12;
        if (ap === 'am' && h === 12) h = 0;
        return h * 60 + mins;
    };

    const open = toMins(matches[0]);
    const close = toMins(matches[1]);
    if (open == null || close == null) return null;
    return { open, close };
}

function getTodayHoursRange(settings) {
    const day = new Date().getDay(); // 0=Sun
    const source = settings || SITE_SETTINGS || {};
    if (day === 0) {
        return source.opening_hours_sunday || '9:00am – 8:00pm';
    }
    if (day === 6) {
        return source.opening_hours_saturday || '8:00am – 9:00pm';
    }
    return source.opening_hours_mon_fri || '8:00am – 9:00pm';
}

function isStoreOpenNow(settings) {
    const window = parseHoursRangeToMinutes(getTodayHoursRange(settings));
    if (!window) return null;
    const now = new Date();
    const mins = now.getHours() * 60 + now.getMinutes();
    return mins >= window.open && mins < window.close;
}

function updateOpenNowBadge(settings) {
    const badge = document.getElementById('open-now-badge');
    if (!badge) return;
    const open = isStoreOpenNow(settings || SITE_SETTINGS);
    if (open == null) {
        badge.textContent = '';
        badge.className = 'open-badge';
        return;
    }
    badge.textContent = open ? '● Open Now' : '● Currently Closed';
    badge.className = 'open-badge ' + (open ? 'open' : 'closed');
}

function getWhatsAppNumber() {
    return digitsOnly(SITE_SETTINGS.whatsapp_number) || '447802617847';
}
