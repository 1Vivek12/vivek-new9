import React, { useState, useEffect } from 'react';

interface Destination {
  id: string;
  destination_type: string;
  display_name: string;
  is_active: boolean;
}

interface ConnectedAccount {
  id: string;
  destination_id: string;
  account_type: string;
  platform_account_id: string;
  account_name: string;
  connection_status: string;
  is_deleted: boolean;
}

interface PlatformPayload {
  id?: string;
  destination_type: string;
  account_id: string;
  adapted_title: string;
  adapted_description: string;
  adapted_caption: string;
  target_aspect_ratio: string;
  custom_metadata?: Record<string, any>;
}

interface PublishingPackage {
  id: string;
  canonical_title: string;
  canonical_description: string;
  canonical_caption?: string;
  tags: string[];
  status: string;
  current_approval_id?: string;
  created_at: string;
  payloads: PlatformPayload[];
}

interface PublishedItem {
  id: string;
  destination_type: string;
  external_item_id: string;
  external_url: string;
  published_at: string;
  platform_state: string;
}

export const PublishingCommandCenter: React.FC = () => {
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [accounts, setAccounts] = useState<ConnectedAccount[]>([]);
  const [packages, setPackages] = useState<PublishingPackage[]>([]);
  const [publishedItems, setPublishedItems] = useState<PublishedItem[]>([]);
  const [selectedPackage, setSelectedPackage] = useState<PublishingPackage | null>(null);

  // Form states
  const [activePlatformTab, setActivePlatformTab] = useState<string>('YOUTUBE');
  const [canonicalTitle, setCanonicalTitle] = useState('');
  const [canonicalDescription, setCanonicalDescription] = useState('');
  const [canonicalCaption, setCanonicalCaption] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Platform adaptations
  const [ytTitle, setYtTitle] = useState('');
  const [ytDescription, setYtDescription] = useState('');
  const [ytIsShort, setYtIsShort] = useState(false);
  const [fbMessage, setFbMessage] = useState('');
  const [igCaption, setIgCaption] = useState('');
  const [igIsReel, setIgIsReel] = useState(true);
  const [waRecipients, setWaRecipients] = useState('+919876543210, +919876543211');
  const [webTitle, setWebTitle] = useState('');
  const [webBody, setWebBody] = useState('');

  // Connect Channel Modal
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [selectedDestId, setSelectedDestId] = useState('');
  const [accName, setAccName] = useState('');
  const [platformAccId, setPlatformAccId] = useState('');
  const [manualToken, setManualToken] = useState('');

  const tenantId = '00000000-0000-0000-0000-000000000001'; // Default tenant

  useEffect(() => {
    fetchDestinations();
    fetchAccounts();
    fetchPackages();
    fetchPublishedItems();
  }, []);

  const fetchDestinations = async () => {
    try {
      const res = await fetch('/api/v1/publishing/destinations', {
        headers: { 'X-Tenant-ID': tenantId },
      });
      if (res.ok) {
        const data = await res.json();
        setDestinations(data);
        if (data.length > 0 && !selectedDestId) {
          setSelectedDestId(data[0].id);
        }
      }
    } catch (err) {
      console.error('Error fetching destinations', err);
    }
  };

  const fetchAccounts = async () => {
    try {
      const res = await fetch('/api/v1/publishing/accounts', {
        headers: { 'X-Tenant-ID': tenantId },
      });
      if (res.ok) {
        const data = await res.json();
        setAccounts(data);
      }
    } catch (err) {
      console.error('Error fetching accounts', err);
    }
  };

  const fetchPackages = async () => {
    try {
      const res = await fetch('/api/v1/publishing/packages', {
        headers: { 'X-Tenant-ID': tenantId },
      });
      if (res.ok) {
        const data = await res.json();
        setPackages(data);
        if (data.length > 0 && !selectedPackage) {
          selectPackageForEditing(data[0]);
        }
      }
    } catch (err) {
      console.error('Error fetching packages', err);
    }
  };

  const fetchPublishedItems = async () => {
    try {
      const res = await fetch('/api/v1/publishing/published-items', {
        headers: { 'X-Tenant-ID': tenantId },
      });
      if (res.ok) {
        const data = await res.json();
        setPublishedItems(data);
      }
    } catch (err) {
      console.error('Error fetching published items', err);
    }
  };

  const selectPackageForEditing = (pkg: PublishingPackage) => {
    setSelectedPackage(pkg);
    setCanonicalTitle(pkg.canonical_title);
    setCanonicalDescription(pkg.canonical_description);
    setCanonicalCaption(pkg.canonical_caption || '');
    setTagsInput((pkg.tags || []).join(', '));

    // Populate platform fields if payloads exist
    const yt = pkg.payloads.find((p) => p.destination_type === 'YOUTUBE');
    if (yt) {
      setYtTitle(yt.adapted_title);
      setYtDescription(yt.adapted_description);
      setYtIsShort(yt.custom_metadata?.is_short || false);
    } else {
      setYtTitle(pkg.canonical_title);
      setYtDescription(pkg.canonical_description);
    }

    const fb = pkg.payloads.find((p) => p.destination_type === 'FACEBOOK');
    if (fb) setFbMessage(fb.adapted_description || fb.adapted_caption);
    else setFbMessage(pkg.canonical_description);

    const ig = pkg.payloads.find((p) => p.destination_type === 'INSTAGRAM');
    if (ig) {
      setIgCaption(ig.adapted_caption || ig.adapted_description);
      setIgIsReel(ig.custom_metadata?.is_reel ?? true);
    } else {
      setIgCaption(pkg.canonical_caption || pkg.canonical_description);
    }

    const wa = pkg.payloads.find((p) => p.destination_type === 'WHATSAPP');
    if (wa) {
      const recs = wa.custom_metadata?.recipients || [];
      setWaRecipients(recs.join(', '));
    }

    const web = pkg.payloads.find((p) => p.destination_type === 'WEBSITE');
    if (web) {
      setWebTitle(web.adapted_title);
      setWebBody(web.adapted_description);
    } else {
      setWebTitle(pkg.canonical_title);
      setWebBody(pkg.canonical_description);
    }

    setValidationResult(null);
  };

  const handleCreatePackage = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setStatusMessage(null);
    try {
      const parsedTags = tagsInput.split(',').map((t) => t.trim()).filter(Boolean);
      const res = await fetch('/api/v1/publishing/packages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Tenant-ID': tenantId },
        body: JSON.stringify({
          story_id: '00000000-0000-0000-0000-000000000002', // Mock linked story
          story_version_id: '00000000-0000-0000-0000-000000000003',
          destination_types: ['YOUTUBE', 'FACEBOOK', 'INSTAGRAM', 'WHATSAPP', 'WEBSITE'],
          account_ids: accounts.map((a) => a.id),
          canonical_title: canonicalTitle,
          canonical_description: canonicalDescription,
          canonical_caption: canonicalCaption,
          tags: parsedTags,
        }),
      });
      if (res.ok) {
        const newPkg = await res.json();
        setStatusMessage('✨ Publication Package created successfully in DRAFT state.');
        fetchPackages();
        selectPackageForEditing(newPkg);
      } else {
        const err = await res.json();
        setStatusMessage(`❌ Error: ${err.detail || 'Failed to create package'}`);
      }
    } catch (err: any) {
      setStatusMessage(`❌ Error: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSavePlatformPayload = async () => {
    if (!selectedPackage) return;
    setIsSubmitting(true);
    try {
      const targetAcc = accounts.find((a) => {
        const d = destinations.find((dest) => dest.id === a.destination_id);
        return d && d.destination_type === activePlatformTab;
      }) || accounts[0];

      if (!targetAcc) {
        setStatusMessage(`❌ No connected account found for ${activePlatformTab}. Please connect an account first.`);
        setIsSubmitting(false);
        return;
      }

      let payloadData: any = {
        destination_type: activePlatformTab,
        account_id: targetAcc.id,
      };

      if (activePlatformTab === 'YOUTUBE') {
        payloadData.adapted_title = ytTitle;
        payloadData.adapted_description = ytDescription;
        payloadData.target_aspect_ratio = ytIsShort ? '9:16' : '16:9';
        payloadData.custom_metadata = { is_short: ytIsShort, tags: tagsInput.split(',').map((t) => t.trim()) };
      } else if (activePlatformTab === 'FACEBOOK') {
        payloadData.adapted_title = canonicalTitle;
        payloadData.adapted_description = fbMessage;
        payloadData.target_aspect_ratio = '16:9';
      } else if (activePlatformTab === 'INSTAGRAM') {
        payloadData.adapted_title = canonicalTitle;
        payloadData.adapted_caption = igCaption;
        payloadData.target_aspect_ratio = '9:16';
        payloadData.custom_metadata = { is_reel: igIsReel };
      } else if (activePlatformTab === 'WHATSAPP') {
        payloadData.adapted_title = canonicalTitle;
        payloadData.adapted_description = canonicalDescription;
        payloadData.custom_metadata = {
          recipients: waRecipients.split(',').map((r) => r.trim()).filter(Boolean),
        };
      } else if (activePlatformTab === 'WEBSITE') {
        payloadData.adapted_title = webTitle;
        payloadData.adapted_description = webBody;
        payloadData.target_aspect_ratio = '16:9';
      }

      const res = await fetch(`/api/v1/publishing/packages/${selectedPackage.id}/payloads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Tenant-ID': tenantId },
        body: JSON.stringify(payloadData),
      });

      if (res.ok) {
        setStatusMessage(`✅ ${activePlatformTab} adaptation saved. Note: Prior approvals invalidated on edits.`);
        fetchPackages();
      } else {
        const err = await res.json();
        setStatusMessage(`❌ Failed to save payload: ${err.detail}`);
      }
    } catch (err: any) {
      setStatusMessage(`❌ Error: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleValidate = async () => {
    if (!selectedPackage) return;
    try {
      const res = await fetch(`/api/v1/publishing/packages/${selectedPackage.id}/validate`, {
        method: 'POST',
        headers: { 'X-Tenant-ID': tenantId },
      });
      if (res.ok) {
        const data = await res.json();
        setValidationResult(data);
        setStatusMessage(
          data.is_valid
            ? '✅ All platform constraints and rights policies passed verification!'
            : `⚠️ Validation identified ${data.validation_errors.length} issue(s).`
        );
      }
    } catch (err: any) {
      setStatusMessage(`❌ Validation error: ${err.message}`);
    }
  };

  const handleApprove = async (action: 'APPROVE' | 'REJECT') => {
    if (!selectedPackage) return;
    try {
      const res = await fetch(`/api/v1/publishing/packages/${selectedPackage.id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Tenant-ID': tenantId },
        body: JSON.stringify({
          action,
          rejection_reason: action === 'REJECT' ? 'Needs revision by editorial desk' : undefined,
        }),
      });
      if (res.ok) {
        setStatusMessage(`🛡️ Human approval ledger recorded: Package marked ${action}.`);
        fetchPackages();
      } else {
        const err = await res.json();
        setStatusMessage(`❌ Action failed: ${err.detail}`);
      }
    } catch (err: any) {
      setStatusMessage(`❌ Approval error: ${err.message}`);
    }
  };

  const handlePublishNow = async () => {
    if (!selectedPackage) return;
    setIsSubmitting(true);
    setStatusMessage('🚀 Dispatching package across distribution network...');
    try {
      const res = await fetch(`/api/v1/publishing/packages/${selectedPackage.id}/publish`, {
        method: 'POST',
        headers: { 'X-Tenant-ID': tenantId },
      });
      if (res.ok) {
        const job = await res.json();
        setStatusMessage(`🎉 Publishing job dispatched! Status: ${job.job_status}`);
        fetchPackages();
        fetchPublishedItems();
      } else {
        const err = await res.json();
        setStatusMessage(`❌ Publish dispatch failed: ${err.detail}`);
      }
    } catch (err: any) {
      setStatusMessage(`❌ Dispatch error: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConnectAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/v1/publishing/accounts/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Tenant-ID': tenantId },
        body: JSON.stringify({
          destination_id: selectedDestId,
          account_name: accName,
          platform_account_id: platformAccId,
          access_token: manualToken,
          account_type: 'CHANNEL',
        }),
      });
      if (res.ok) {
        setShowConnectModal(false);
        setAccName('');
        setPlatformAccId('');
        setManualToken('');
        fetchAccounts();
        setStatusMessage('🔗 Account connected and encrypted credentials safely vaulted.');
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Top Banner & Destinations */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '1rem' }}>
        {['YOUTUBE', 'FACEBOOK', 'INSTAGRAM', 'WHATSAPP', 'WEBSITE'].map((dtype) => {
          const dest = destinations.find((d) => d.destination_type === dtype);
          const accs = accounts.filter((a) => {
            const d = destinations.find((dest) => dest.id === a.destination_id);
            return d && d.destination_type === dtype;
          });
          const isConnected = accs.length > 0;
          return (
            <div
              key={dtype}
              style={{
                background: 'var(--bg-card, #1e1e24)',
                padding: '1rem',
                borderRadius: '8px',
                border: isConnected ? '1px solid #10b981' : '1px solid #374151',
                position: 'relative',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>{dest?.display_name || dtype}</span>
                <span
                  style={{
                    fontSize: '0.7rem',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    background: isConnected ? '#065f46' : '#374151',
                    color: isConnected ? '#34d399' : '#9ca3af',
                  }}
                >
                  {isConnected ? 'CONNECTED' : 'DISCONNECTED'}
                </span>
              </div>
              <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#9ca3af' }}>
                {accs.length} account(s) active
              </div>
            </div>
          );
        })}
      </div>

      {statusMessage && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: '6px',
            background: '#26262e',
            border: '1px solid #4f46e5',
            fontSize: '0.9rem',
          }}
        >
          {statusMessage}
        </div>
      )}

      {/* Main Workspace Grid: Package Composer & Platform Adaptations */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '2rem' }}>
        {/* Left Column: Package List & Canonical Composer */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>📦 Publishing Packages</h2>
            <button
              onClick={() => setShowConnectModal(true)}
              style={{
                padding: '4px 10px',
                fontSize: '0.8rem',
                background: 'var(--accent-red, #dc2626)',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              + Connect Channel
            </button>
          </div>

          <div
            style={{
              maxHeight: '220px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
            }}
          >
            {packages.map((pkg) => {
              const isSel = selectedPackage?.id === pkg.id;
              return (
                <div
                  key={pkg.id}
                  onClick={() => selectPackageForEditing(pkg)}
                  style={{
                    padding: '0.75rem',
                    borderRadius: '6px',
                    background: isSel ? '#2e2e38' : '#1e1e24',
                    border: isSel ? '1px solid #ef4444' : '1px solid #374151',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{pkg.canonical_title}</span>
                    <span
                      style={{
                        fontSize: '0.7rem',
                        padding: '1px 5px',
                        borderRadius: '3px',
                        background: pkg.status === 'APPROVED' ? '#065f46' : '#4b5563',
                        color: '#fff',
                      }}
                    >
                      {pkg.status}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '4px' }}>
                    Payloads: {pkg.payloads?.length || 0} destinations
                  </div>
                </div>
              );
            })}
          </div>

          {/* New Package Composer Form */}
          <div
            style={{
              background: '#1e1e24',
              padding: '1.25rem',
              borderRadius: '8px',
              border: '1px solid #374151',
            }}
          >
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '1rem' }}>
              Create New Broadcast Package
            </h3>
            <form onSubmit={handleCreatePackage} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Canonical Title</label>
                <input
                  type="text"
                  required
                  value={canonicalTitle}
                  onChange={(e) => setCanonicalTitle(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    background: '#2b2b36',
                    border: '1px solid #4b5563',
                    color: '#fff',
                    borderRadius: '4px',
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Canonical Description / Body</label>
                <textarea
                  rows={3}
                  value={canonicalDescription}
                  onChange={(e) => setCanonicalDescription(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    background: '#2b2b36',
                    border: '1px solid #4b5563',
                    color: '#fff',
                    borderRadius: '4px',
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Tags (comma-separated)</label>
                <input
                  type="text"
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                  placeholder="news, gorakhpur, live, breaking"
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    background: '#2b2b36',
                    border: '1px solid #4b5563',
                    color: '#fff',
                    borderRadius: '4px',
                  }}
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                style={{
                  marginTop: '0.5rem',
                  padding: '0.5rem',
                  background: 'var(--accent-red, #dc2626)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Assemble Package (Draft)
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Platform Adaptation Tabs, Validation & Approval Gates */}
        <div
          style={{
            background: '#1e1e24',
            padding: '1.5rem',
            borderRadius: '8px',
            border: '1px solid #374151',
            display: 'flex',
            flexDirection: 'column',
            gap: '1.5rem',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>
              Platform Adaptations {selectedPackage ? `(${selectedPackage.canonical_title})` : ''}
            </h2>

            {/* Validation & Approval action buttons */}
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                onClick={handleValidate}
                style={{
                  padding: '4px 10px',
                  fontSize: '0.8rem',
                  background: '#374151',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                🔍 Run Validation
              </button>

              {selectedPackage?.status !== 'APPROVED' ? (
                <button
                  onClick={() => handleApprove('APPROVE')}
                  style={{
                    padding: '4px 10px',
                    fontSize: '0.8rem',
                    background: '#059669',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '4px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  ✍️ Sign Human Approval
                </button>
              ) : (
                <button
                  onClick={handlePublishNow}
                  disabled={isSubmitting}
                  style={{
                    padding: '4px 12px',
                    fontSize: '0.85rem',
                    background: '#ef4444',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '4px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  🚀 Publish Now
                </button>
              )}
            </div>
          </div>

          {/* Platform Switcher Tabs */}
          <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid #374151', paddingBottom: '0.5rem' }}>
            {['YOUTUBE', 'FACEBOOK', 'INSTAGRAM', 'WHATSAPP', 'WEBSITE'].map((p) => (
              <button
                key={p}
                onClick={() => setActivePlatformTab(p)}
                style={{
                  background: activePlatformTab === p ? '#dc2626' : 'transparent',
                  border: 'none',
                  color: '#fff',
                  padding: '4px 12px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontWeight: activePlatformTab === p ? 700 : 500,
                  fontSize: '0.85rem',
                }}
              >
                {p}
              </button>
            ))}
          </div>

          {/* Tab Content Panels */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {activePlatformTab === 'YOUTUBE' && (
              <>
                <div>
                  <label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>YouTube Title (max 100 chars)</label>
                  <input
                    type="text"
                    maxLength={100}
                    value={ytTitle}
                    onChange={(e) => setYtTitle(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      background: '#2b2b36',
                      border: '1px solid #4b5563',
                      color: '#fff',
                      borderRadius: '4px',
                    }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Description (max 5000 chars)</label>
                  <textarea
                    rows={4}
                    maxLength={5000}
                    value={ytDescription}
                    onChange={(e) => setYtDescription(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      background: '#2b2b36',
                      border: '1px solid #4b5563',
                      color: '#fff',
                      borderRadius: '4px',
                    }}
                  />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="checkbox"
                    id="ytShort"
                    checked={ytIsShort}
                    onChange={(e) => setYtIsShort(e.target.checked)}
                  />
                  <label htmlFor="ytShort" style={{ fontSize: '0.85rem' }}>
                    Publish as YouTube Short (Aspect Ratio: 9:16 vertical, duration &le; 180s)
                  </label>
                </div>
              </>
            )}

            {activePlatformTab === 'FACEBOOK' && (
              <div>
                <label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Facebook Post Message / Video Caption</label>
                <textarea
                  rows={4}
                  value={fbMessage}
                  onChange={(e) => setFbMessage(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    background: '#2b2b36',
                    border: '1px solid #4b5563',
                    color: '#fff',
                    borderRadius: '4px',
                  }}
                />
              </div>
            )}

            {activePlatformTab === 'INSTAGRAM' && (
              <>
                <div>
                  <label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Instagram Caption (max 2200 chars)</label>
                  <textarea
                    rows={4}
                    maxLength={2200}
                    value={igCaption}
                    onChange={(e) => setIgCaption(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      background: '#2b2b36',
                      border: '1px solid #4b5563',
                      color: '#fff',
                      borderRadius: '4px',
                    }}
                  />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="checkbox"
                    id="igReel"
                    checked={igIsReel}
                    onChange={(e) => setIgIsReel(e.target.checked)}
                  />
                  <label htmlFor="igReel" style={{ fontSize: '0.85rem' }}>
                    Publish as Instagram Reel (Aspect Ratio: 9:16, max 90s)
                  </label>
                </div>
              </>
            )}

            {activePlatformTab === 'WHATSAPP' && (
              <>
                <div>
                  <label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>
                    Recipient Phone Numbers (E.164, comma-separated)
                  </label>
                  <input
                    type="text"
                    value={waRecipients}
                    onChange={(e) => setWaRecipients(e.target.value)}
                    placeholder="+919876543210, +919876543211"
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      background: '#2b2b36',
                      border: '1px solid #4b5563',
                      color: '#fff',
                      borderRadius: '4px',
                    }}
                  />
                </div>
                <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>
                  Application safety rate limit: 20 messages / second token bucket enforcement active.
                </div>
              </>
            )}

            {activePlatformTab === 'WEBSITE' && (
              <>
                <div>
                  <label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Article Headline</label>
                  <input
                    type="text"
                    value={webTitle}
                    onChange={(e) => setWebTitle(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      background: '#2b2b36',
                      border: '1px solid #4b5563',
                      color: '#fff',
                      borderRadius: '4px',
                    }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Full Article Body</label>
                  <textarea
                    rows={5}
                    value={webBody}
                    onChange={(e) => setWebBody(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      background: '#2b2b36',
                      border: '1px solid #4b5563',
                      color: '#fff',
                      borderRadius: '4px',
                    }}
                  />
                </div>
              </>
            )}

            <button
              onClick={handleSavePlatformPayload}
              disabled={isSubmitting}
              style={{
                alignSelf: 'flex-start',
                padding: '0.5rem 1rem',
                background: '#4f46e5',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Save {activePlatformTab} Adaptation
            </button>
          </div>

          {/* Validation Result Box */}
          {validationResult && (
            <div
              style={{
                padding: '0.75rem',
                borderRadius: '6px',
                background: validationResult.is_valid ? '#064e3b' : '#7f1d1d',
                border: validationResult.is_valid ? '1px solid #059669' : '1px solid #dc2626',
              }}
            >
              <div style={{ fontWeight: 700, fontSize: '0.85rem' }}>
                Manifest SHA-256 Hash: {validationResult.manifest_hash?.substring(0, 24)}...
              </div>
              {validationResult.validation_errors.length > 0 && (
                <ul style={{ margin: '0.5rem 0 0 1rem', fontSize: '0.8rem' }}>
                  {validationResult.validation_errors.map((err: string, i: number) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Live Distribution Ledger */}
      <div
        style={{
          background: '#1e1e24',
          padding: '1.25rem',
          borderRadius: '8px',
          border: '1px solid #374151',
        }}
      >
        <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem' }}>
          🌐 Real-Time Distribution Ledger &amp; Published Items
        </h3>
        {publishedItems.length === 0 ? (
          <div style={{ color: '#9ca3af', fontSize: '0.85rem' }}>
            No external items published yet. Approve and dispatch a package above!
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {publishedItems.map((item) => (
              <div
                key={item.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.5rem 0.75rem',
                  background: '#2b2b36',
                  borderRadius: '4px',
                  fontSize: '0.85rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <span
                    style={{
                      fontWeight: 700,
                      color: '#ef4444',
                    }}
                  >
                    [{item.destination_type}]
                  </span>
                  <span>Item ID: {item.external_item_id}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <a
                    href={item.external_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: '#60a5fa', textDecoration: 'none' }}
                  >
                    🔗 View Post &rarr;
                  </a>
                  <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>
                    {new Date(item.published_at).toLocaleTimeString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Connect Channel Modal */}
      {showConnectModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
          }}
        >
          <div
            style={{
              background: '#1e1e24',
              padding: '1.5rem',
              borderRadius: '8px',
              border: '1px solid #4b5563',
              width: '420px',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
            }}
          >
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Connect Publishing Channel</h3>
            <form onSubmit={handleConnectAccount} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Target Platform</label>
                <select
                  value={selectedDestId}
                  onChange={(e) => setSelectedDestId(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    background: '#2b2b36',
                    border: '1px solid #4b5563',
                    color: '#fff',
                    borderRadius: '4px',
                  }}
                >
                  {destinations.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.display_name} ({d.destination_type})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Account / Channel Name</label>
                <input
                  type="text"
                  required
                  placeholder="News 9 Official"
                  value={accName}
                  onChange={(e) => setAccName(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    background: '#2b2b36',
                    border: '1px solid #4b5563',
                    color: '#fff',
                    borderRadius: '4px',
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Platform Account ID / Page ID</label>
                <input
                  type="text"
                  required
                  placeholder="UC12345678 or 10987654321"
                  value={platformAccId}
                  onChange={(e) => setPlatformAccId(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    background: '#2b2b36',
                    border: '1px solid #4b5563',
                    color: '#fff',
                    borderRadius: '4px',
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Access Token / System User Secret</label>
                <input
                  type="password"
                  placeholder="Bearer token (will be vaulted with AES-256-GCM)"
                  value={manualToken}
                  onChange={(e) => setManualToken(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    background: '#2b2b36',
                    border: '1px solid #4b5563',
                    color: '#fff',
                    borderRadius: '4px',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setShowConnectModal(false)}
                  style={{
                    padding: '0.5rem 1rem',
                    background: '#374151',
                    border: 'none',
                    color: '#fff',
                    borderRadius: '4px',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{
                    padding: '0.5rem 1rem',
                    background: '#dc2626',
                    border: 'none',
                    color: '#fff',
                    borderRadius: '4px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Save &amp; Vault Key
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
