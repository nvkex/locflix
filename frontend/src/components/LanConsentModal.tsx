import { useLan } from '../lan'

export function LanConsentModal() {
  const { share, grantOwnerConsent, setShareEnabled } = useLan()

  if (!share?.share_enabled || share.owner_consented) return null

  return (
    <div className="lan-modal-backdrop" role="presentation">
      <div className="lan-modal glass" role="dialog" aria-labelledby="lan-consent-title">
        <p className="lan-modal-kicker">LAN sharing</p>
        <h2 id="lan-consent-title">Allow streaming on your network?</h2>
        <p className="muted">
          Other devices on this Wi‑Fi will be able to browse and play media from{' '}
          <strong>{share.share_name}</strong> ({share.lan_ip}:{share.api_port}) until you turn
          sharing off. Approve once for this session.
        </p>
        <div className="lan-modal-actions">
          <button
            type="button"
            className="btn"
            onClick={() => void setShareEnabled(false)}
          >
            Not now
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void grantOwnerConsent(true)}
          >
            Allow this session
          </button>
        </div>
      </div>
    </div>
  )
}
