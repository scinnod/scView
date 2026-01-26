<!--
SPDX-License-Identifier: AGPL-3.0-or-later
SPDX-FileCopyrightText: 2024-2026 David Kleinhans, Jade University of Applied Sciences
-->

# LaTeX Templates Directory

This directory contains LaTeX template fragments for customizing PDF exports.

## Customization

### Recommended: Use Overrides

Place your `.tex` files in `overrides/latex_templates/` and mount via `docker-compose.override.yml`:

```yaml
- ./overrides/latex_templates:/app/user_files/latex_templates:ro
```

### Available Template Files

| File | Purpose |
|------|---------|
| `header.tex` | Page header configuration |
| `footer.tex` | Page footer configuration |
| `colors.tex` | Color definitions |
| `titlepage.tex` | Custom title page |
| `fonts.tex` | Font configuration |

### Example: Custom Header

```latex
% header.tex
\fancyhead[L]{\includegraphics[height=1cm]{logo.png}}
\fancyhead[R]{\textbf{Service Catalogue}}
\fancyfoot[C]{\thepage}
```

### Example: Custom Colors

```latex
% colors.tex
\definecolor{primarycolor}{RGB}{0,102,204}
\hypersetup{
    colorlinks=true,
    linkcolor=primarycolor,
    urlcolor=primarycolor
}
```

## Logo Files

Logos are stored in `static/logos/`, not here. Reference them by filename:

```latex
\includegraphics[height=1cm]{logo.png}
```

## After Changes

```bash
docker-compose restart itsm
```

## See Also

- [../README.md](../README.md) - User files overview
- [overrides/README.md](../../../../overrides/README.md) - Override directory
