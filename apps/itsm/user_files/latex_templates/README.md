# Custom LaTeX Template Fragments

Place custom LaTeX fragments here to customize PDF export appearance.

## Purpose

Override or extend the default LaTeX templates for service catalogue PDF exports with your organization's branding and layout preferences.

## How It Works

The main templates in `apps/itsm/ServiceCatalogue/templates/ServiceCatalogue/*.tex` can include custom fragments from this directory to add organization-specific styling.

## Common Customizations

### Header and Footer

Create `header.tex`:
```latex
\fancyhead[L]{\includegraphics[height=1cm]{organization_logo_color.jpg}}
\fancyhead[R]{\textbf{Service Catalogue}}
\fancyfoot[C]{\thepage}
\fancyfoot[L]{\small Your Organization Name}
\fancyfoot[R]{\small \today}
```

### Title Page

Create `titlepage.tex`:
```latex
\begin{titlepage}
    \centering
    \vspace*{2cm}
    
    \includegraphics[width=0.6\textwidth]{organization_logo_color.jpg}
    
    \vspace{2cm}
    {\huge\bfseries IT Service Catalogue\par}
    
    \vspace{1cm}
    {\Large Your Organization Name\par}
    
    \vfill
    
    {\large \today\par}
\end{titlepage}
```

### Custom Colors

Create `colors.tex`:
```latex
\definecolor{primarycolor}{RGB}{0,102,204}
\definecolor{secondarycolor}{RGB}{255,102,0}
\definecolor{headingcolor}{RGB}{51,51,51}

\hypersetup{
    colorlinks=true,
    linkcolor=primarycolor,
    urlcolor=primarycolor,
    citecolor=primarycolor
}
```

### Font Configuration

Create `fonts.tex`:
```latex
\usepackage{fontspec}
\setmainfont{Your Corporate Font}
\setsansfont{Your Sans Font}
\setmonofont{Courier New}
```

## Including Custom Fragments

To use these fragments, modify the main template files to include them:

```latex
% In services_listed_en.tex or services_listed_de.tex
\documentclass[a4paper,11pt]{article}

% Include custom fragments
\input{/app/latex_templates/colors}
\input{/app/latex_templates/fonts}

\begin{document}
\input{/app/latex_templates/titlepage}
\input{/app/latex_templates/header}

% Rest of template...
\end{document}
```

## Docker Mounting

These fragments would need to be mounted in the container (if you want to use them). Update `docker-compose.yml`:

```yaml
itsm:
  volumes:
    - ./user_files/latex_templates:/app/latex_templates:ro
```

## File Naming

Use descriptive names without spaces:
- `header.tex` - Header configuration
- `footer.tex` - Footer configuration
- `titlepage.tex` - Custom title page
- `colors.tex` - Color definitions
- `fonts.tex` - Font configuration
- `packages.tex` - Additional LaTeX packages
- `macros.tex` - Custom LaTeX macros

## Testing

After creating custom fragments:

1. Restart the application: `docker-compose restart itsm`
2. Generate a PDF export
3. Review the output
4. Iterate on styling

## Debugging LaTeX Errors

If PDF generation fails:

```bash
# Check LaTeX logs in container
docker-compose exec itsm cat /tmp/latex-errors.log

# Run LaTeX manually to see errors
docker-compose exec itsm bash
cd /tmp
pdflatex your-test.tex
```

Common issues:
- Missing packages: Install in Dockerfile
- Font not found: Ensure fonts are available in container
- Syntax errors: Validate LaTeX syntax
- Missing graphics: Verify logo files are in mounted directory

## Best Practices

1. **Test incrementally**: Add one customization at a time
2. **Use comments**: Document what each fragment does
3. **Keep it simple**: Complex LaTeX can be fragile
4. **Maintain backups**: Keep working versions
5. **Document dependencies**: Note required packages

## Example: Complete Customization

**1. Create color scheme (`colors.tex`):**
```latex
\definecolor{brandblue}{RGB}{0,82,156}
\definecolor{brandorange}{RGB}{255,121,0}
```

**2. Create header (`header.tex`):**
```latex
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\color{brandblue}\textbf{IT Services}}
\fancyhead[R]{\includegraphics[height=0.8cm]{organization_logo_color.jpg}}
\fancyfoot[C]{\color{brandblue}\thepage}
```

**3. Update main template:**
```latex
\documentclass[a4paper,11pt]{article}
\input{/app/latex_templates/colors}
\input{/app/latex_templates/header}
\begin{document}
% Your content
\end{document}
```

## Resources

- [LaTeX Documentation](https://www.latex-project.org/help/documentation/)
- [CTAN Package Repository](https://ctan.org/)
- [LaTeX Color Documentation](https://ctan.org/pkg/xcolor)
- [fancyhdr Package](https://ctan.org/pkg/fancyhdr)
