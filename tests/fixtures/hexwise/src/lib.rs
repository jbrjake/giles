/// Core color-matching logic for hexwise.
///
/// Parses hex color codes and finds the nearest CSS named color
/// using Euclidean distance in RGB space.

/// Parse a hex color string like "#ff6347" into (R, G, B).
pub fn parse_hex(input: &str) -> Result<(u8, u8, u8), String> {
    let hex = input.trim_start_matches('#');
    if hex.len() != 6 {
        return Err(format!("expected 6 hex digits, got {}", hex.len()));
    }
    let r = u8::from_str_radix(&hex[0..2], 16).map_err(|e| e.to_string())?;
    let g = u8::from_str_radix(&hex[2..4], 16).map_err(|e| e.to_string())?;
    let b = u8::from_str_radix(&hex[4..6], 16).map_err(|e| e.to_string())?;
    Ok((r, g, b))
}
