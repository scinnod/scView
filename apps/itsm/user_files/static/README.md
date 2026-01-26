# Custom Static Files

Place additional static files here for organization-specific branding and customization.

## Purpose

This directory is for static assets that are specific to your organization and should not be part of the core application codebase.

## What to Put Here

### CSS Customization
- `custom.css` - Override default styles
- `branding.css` - Organization color schemes
- `theme.css` - Custom theme

### Images
- `favicon.ico` - Custom favicon
- `hero-image.jpg` - Landing page images
- `backgrounds/` - Background images
- `icons/` - Custom icons

### JavaScript
- `custom.js` - Custom JavaScript functionality
- `analytics.js` - Analytics tracking code

### Fonts
- Custom web fonts for branding

## File Structure Example

```
user_files/static/
├── css/
│   ├── custom.css
│   └── branding.css
├── js/
│   └── custom.js
├── images/
│   ├── favicon.ico
│   └── hero.jpg
└── fonts/
    └── YourFont.woff2
```

## Usage in Templates

Files in this directory are available at `/static/custom/` URL path:

```html
<!-- In your Django templates -->
<link rel="stylesheet" href="{% static 'custom/css/branding.css' %}">
<script src="{% static 'custom/js/custom.js' %}"></script>
<img src="{% static 'custom/images/hero.jpg' %}" alt="Hero">
```

## Docker Mounting

These files are mounted in the container:

```yaml
nginx:
  volumes:
    - ./user_files/static:/vol/staticfiles_itsm/custom:ro
```

## Applying Changes

After adding or modifying files:

```bash
# Restart nginx to pick up new files
docker-compose restart nginx

# Or restart all services
docker-compose restart
```

## Best Practices

1. **Organize by type**: Keep CSS, JS, and images in separate subdirectories
2. **Use meaningful names**: Descriptive filenames make maintenance easier
3. **Optimize files**: Minify CSS/JS, compress images
4. **Version assets**: Consider adding version numbers to force cache refresh
5. **Test thoroughly**: Verify files load correctly after deployment

## Example: Custom Branding

**Create custom CSS:**

```css
/* user_files/static/css/branding.css */

:root {
  --primary-color: #0066cc;
  --secondary-color: #ff6600;
  --font-family: 'Your Custom Font', sans-serif;
}

.navbar {
  background-color: var(--primary-color) !important;
}

.btn-primary {
  background-color: var(--primary-color);
  border-color: var(--primary-color);
}

.footer {
  background-color: var(--secondary-color);
}
```

**Include in base template:**

Edit `apps/itsm/ServiceCatalogue/templates/ServiceCatalogue/services_base.html`:

```html
{% load static %}
<!-- Add in head section -->
<link rel="stylesheet" href="{% static 'custom/css/branding.css' %}">
```

## Cache Busting

To ensure users see updated files after changes:

```html
<!-- Add version parameter -->
<link rel="stylesheet" href="{% static 'custom/css/branding.css' %}?v=2">
```

Or use Django's cache busting features.

## Security Notes

- Don't place sensitive information in static files (they're publicly accessible)
- Validate and sanitize any user-uploaded content
- Use HTTPS to protect data in transit
- Keep third-party libraries updated

## Troubleshooting

**Files not loading:**
- Check file is in the mounted directory: `docker-compose exec nginx ls -la /vol/staticfiles_itsm/custom/`
- Verify nginx configuration includes the path
- Check browser console for 404 errors
- Clear browser cache

**CSS not applying:**
- Check CSS syntax is valid
- Verify file is loaded (check browser DevTools Network tab)
- Ensure selectors are specific enough (may need `!important`)
- Clear Django's static files cache: `docker-compose exec itsm python manage.py collectstatic --clear --noinput`
