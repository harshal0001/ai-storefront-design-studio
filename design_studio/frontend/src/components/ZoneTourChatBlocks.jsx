import { MarkdownText } from "./MarkdownText";
import { ThemePaletteLine } from "./ThemePaletteLine";

/** Zone tour UI embedded in an assistant chat bubble (not a static panel below input). */
export function ZoneTourChatBlocks({
  zoneTour,
  colorOptions = [],
  zoneOptions = [],
  vibeOptions = [],
  themePackages = [],
  onPickOption,
  onExitTour,
  onGotIt,
  onSkipStep,
  loading,
}) {
  if (
    !zoneTour?.active &&
    !colorOptions.length &&
    !zoneOptions.length &&
    !vibeOptions.length &&
    !themePackages.length
  ) {
    return null;
  }

  if (zoneTour?.info_only) {
    return (
      <div className="zone-tour-chat-blocks">
        <button
          type="button"
          className="zone-gotit-btn"
          onClick={() => onGotIt?.()}
          disabled={loading}
        >
          Got it — continue
        </button>
      </div>
    );
  }

  return (
    <div className="zone-tour-chat-blocks">
      {zoneTour && (
        <div className="zone-chat-banner zone-chat-banner--in-message">
          {zoneTour.current_zone_name && <strong>{zoneTour.current_zone_name}</strong>}
          {zoneTour.sub_step_total > 1 && (
            <span className="zone-chat-banner__step">
              Step {(zoneTour.sub_step_index ?? 0) + 1} of {zoneTour.sub_step_total}
            </span>
          )}
          {(zoneTour.theme_context?.palette_line ||
            zoneTour.theme_context?.palette_colors?.length > 0) && (
            <ThemePaletteLine
              themeContext={zoneTour.theme_context}
              className="zone-chat-banner__theme"
            />
          )}
          {zoneTour.theme_context?.mood_line && (
            <span className="zone-chat-banner__mood">
              <MarkdownText text={zoneTour.theme_context.mood_line} />
            </span>
          )}
          {zoneTour.step_explanation && (
            <span className="zone-chat-banner__explain">
              <MarkdownText text={zoneTour.step_explanation} />
            </span>
          )}
          {zoneTour.highlight_hint ? (
            <span className="zone-chat-banner__hint zone-chat-banner__hint--scope">
              <MarkdownText text={zoneTour.highlight_hint} />
            </span>
          ) : zoneTour.highlight_scope === "page" ? (
            <span className="zone-chat-banner__hint zone-chat-banner__hint--page">
              Applies throughout your storefront — use the full preview, not one highlighted box.
            </span>
          ) : zoneTour.highlight_scope === "zone" || zoneTour.highlight_scope === "element" ? (
            <span className="zone-chat-banner__hint">
              Watch the outlined section in the preview →
            </span>
          ) : null}
        </div>
      )}

      {themePackages.length > 0 && (
        <div className="theme-options theme-options--chat">
          {themePackages.map((pkg, j) => (
            <button
              key={pkg.id || j}
              type="button"
              className="theme-card"
              onClick={() =>
                onPickOption?.(pkg.id ? `zone option ${pkg.id}` : `I choose "${pkg.name}"`)
              }
              disabled={loading}
            >
              <div className="theme-name">{pkg.name}</div>
              <div className="theme-desc">
                <MarkdownText text={pkg.what_changes || pkg.description} />
              </div>
              <div className="palette-swatches">
                {(pkg.colors || []).map((color, k) => (
                  <div
                    key={k}
                    className="swatch"
                    style={{ backgroundColor: color.hex }}
                    title={color.name}
                  />
                ))}
              </div>
            </button>
          ))}
        </div>
      )}

      {colorOptions.length > 0 && (
        <div className="color-options color-options--chat">
          {colorOptions.map((opt, j) => {
            const showSection =
              opt.section && (j === 0 || colorOptions[j - 1]?.section !== opt.section);
            return (
              <div key={opt.id || j} className="color-option-group">
                {showSection && <div className="color-section-label">{opt.section}</div>}
                <button
                  type="button"
                  className="color-card"
                  onClick={() =>
                    onPickOption?.(opt.id ? `zone option ${opt.id}` : `I choose "${opt.name}"`)
                  }
                  disabled={loading}
                >
                  <div className="color-preview" style={{ backgroundColor: opt.hex }} />
                  <div className="color-info">
                    <div className="color-name">{opt.name}</div>
                    <div className="color-desc">
                      <MarkdownText text={opt.what_changes || opt.applies_to || opt.description} />
                      {opt.contrast_ratio && (
                        <span className="color-contrast">
                          Contrast {opt.contrast_ratio}
                          {opt.contrast_background ? ` on ${opt.contrast_background}` : ""}
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              </div>
            );
          })}
        </div>
      )}

      {zoneOptions.length > 0 && (
        <div className="zone-options zone-options--chat">
          {zoneOptions.map((opt, j) => (
            <button
              key={opt.id || j}
              type="button"
              className="vibe-pill zone-choice-pill"
              onClick={() =>
                onPickOption?.(opt.id ? `zone option ${opt.id}` : `I choose "${opt.name}"`)
              }
              disabled={loading}
            >
              <span className="vibe-name">{opt.name}</span>
              <span className="vibe-desc">
                <MarkdownText text={opt.what_changes || opt.applies_to || opt.description} />
              </span>
              {opt.sample_prices && (
                <span className="zone-price-sample" aria-label="Sample catalogue prices">
                  {opt.sample_prices}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {vibeOptions.length > 0 && (
        <div className="zone-options zone-options--chat">
          {vibeOptions.map((opt, j) => (
            <button
              key={opt.id || opt.name || j}
              type="button"
              className="vibe-pill zone-choice-pill"
              onClick={() => onPickOption?.(`I'm going for a ${opt.name} vibe`)}
              disabled={loading}
            >
              <span className="vibe-name">{opt.name}</span>
              <span className="vibe-desc">
                <MarkdownText text={opt.description} />
              </span>
            </button>
          ))}
        </div>
      )}

      {zoneTour?.active && (
        <div className="zone-chat-footer-actions">
          {(colorOptions.length > 0 ||
            zoneOptions.length > 0 ||
            vibeOptions.length > 0 ||
            themePackages.length > 0) && (
            <button
              type="button"
              className="zone-surprise-step-btn"
              onClick={() => onPickOption?.("Surprise me with different options!")}
              disabled={loading}
            >
              🎲 Surprise me — show different options
            </button>
          )}
          {zoneTour.can_skip_sub_step && zoneTour.sub_step_total > 1 && (
            <button
              type="button"
              className="zone-skip-step-btn"
              onClick={() => onSkipStep?.()}
              disabled={loading}
            >
              Skip this step
            </button>
          )}
          <p className="zone-chat-or-type zone-chat-or-type--in-message">
            Or describe what you want below — I can adjust the preview or suggest other looks.{" "}
            <button
              type="button"
              className="zone-exit-link"
              onClick={() => onExitTour?.()}
              disabled={loading}
            >
              Exit customization
            </button>
          </p>
        </div>
      )}
    </div>
  );
}
