import { MarkdownText } from "./MarkdownText";

/** Theme context row: markdown headline + named colour swatches (hex never shown as text). */
export function ThemePaletteLine({ themeContext, className }) {
  if (!themeContext?.palette_line && !themeContext?.palette_colors?.length) {
    return null;
  }

  return (
    <span className={className}>
      {themeContext.palette_line && <MarkdownText text={themeContext.palette_line} />}
      {themeContext.palette_colors?.length > 0 && (
        <span className="palette-inline">
          {themeContext.palette_colors.map((c) => (
            <span className="palette-chip" key={c.role}>
              <span
                className="palette-chip__swatch"
                style={{ backgroundColor: c.hex }}
                aria-hidden="true"
              />
              <span className="palette-chip__name">{c.name}</span>
              <span className="palette-chip__role">{c.label}</span>
            </span>
          ))}
        </span>
      )}
    </span>
  );
}
