import React, { useEffect, useMemo, useState } from 'react';
import { CheckSquare, ChevronLeft, Inbox, Mail, MailOpen, RefreshCw, Reply, Search, Square, Trash2, User } from 'lucide-react';
import { Account } from '../types';
import * as api from '../services/api';

type InboxMessage = { uid: string; from_name?: string; from_email?: string; subject?: string; date?: string; unread?: boolean };

export const InboxView: React.FC<{accounts: Account[]; onReply: () => void}> = ({ accounts, onReply }) => {
  const capable = accounts.filter((a: any) => a.imapHost && a.providerType !== 'zeptomail');
  const [accountId, setAccountId] = useState('');
  const [messages, setMessages] = useState<InboxMessage[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [preview, setPreview] = useState<any>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [mobilePane, setMobilePane] = useState<'list' | 'message'>('list');
  const activeId = accountId || String(capable[0]?.id || '');
  const activeAccount = capable.find(a => String(a.id) === activeId);

  const refresh = async () => {
    if (!activeId) return;
    setLoading(true); setError('');
    try { const rows = await api.fetchInbox(activeId, 100); setMessages(Array.isArray(rows) ? rows : []); setSelected([]); }
    catch (e: any) { setError(e.message || 'Incoming mail could not be loaded.'); }
    finally { setLoading(false); }
  };

  useEffect(() => { setPreview(null); setMobilePane('list'); void refresh(); }, [activeId]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return needle ? messages.filter(m => [m.from_name, m.from_email, m.subject, m.date].some(v => String(v || '').toLowerCase().includes(needle))) : messages;
  }, [messages, query]);
  const unreadCount = messages.filter(m => m.unread).length;
  const allVisibleSelected = filtered.length > 0 && filtered.every(m => selected.includes(m.uid));

  const toggleAll = () => {
    const ids = filtered.map(m => m.uid);
    setSelected(current => allVisibleSelected ? current.filter(uid => !ids.includes(uid)) : Array.from(new Set([...current, ...ids])));
  };

  const openMessage = async (uid: string) => {
    setPreviewLoading(true); setError(''); setMobilePane('message');
    try { setPreview(await api.fetchInboxMessage(activeId, uid)); setMessages(current => current.map(m => m.uid === uid ? {...m, unread: false} : m)); }
    catch (e: any) { setError(e.message || 'The message could not be opened.'); }
    finally { setPreviewLoading(false); }
  };

  const bulk = async (action: 'read' | 'unread' | 'delete') => {
    if (!selected.length) return;
    if (action === 'delete' && !window.confirm(`Permanently delete ${selected.length} selected message(s) from this mailbox?`)) return;
    try { await api.inboxBulkAction(activeId, selected, action); if (action === 'delete') setPreview(null); await refresh(); }
    catch (e: any) { setError(e.message || 'Mailbox action failed.'); }
  };

  const reply = () => {
    if (!preview) return;
    sessionStorage.setItem('esp_inbox_reply', JSON.stringify({ recipient: preview.reply_to, subject: preview.subject?.startsWith('Re:') ? preview.subject : `Re: ${preview.subject || ''}`, accountId: activeId }));
    onReply();
  };

  const formatDate = (value?: string) => {
    if (!value) return '';
    const parsed = new Date(value); if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toDateString() === new Date().toDateString() ? parsed.toLocaleTimeString([], {hour:'numeric', minute:'2-digit'}) : parsed.toLocaleDateString([], {month:'short', day:'numeric'});
  };

  const safeHtmlDocument = (html: string) => `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: cid:; style-src 'unsafe-inline'; font-src data:; base-uri 'none'; form-action 'none'"><style>html{color-scheme:light;-webkit-text-size-adjust:100%}body{margin:0;padding:24px;color:#1e293b;background:#fff;overflow-wrap:anywhere}body,table,td,th,div,p,span,a,li{font-family:Arial,Helvetica,sans-serif!important;font-size:16px!important;line-height:1.6!important;letter-spacing:normal!important}h1{font-size:26px!important;line-height:1.3!important}h2{font-size:23px!important;line-height:1.35!important}h3{font-size:20px!important;line-height:1.4!important}small{font-size:14px!important}img{max-width:100%;height:auto}table{max-width:100%}a{color:#0369a1}</style></head><body>${html}</body></html>`;

  if (!capable.length) return <div className="p-8 max-w-7xl mx-auto"><div className="border border-amber-500/30 bg-amber-500/10 rounded-2xl p-8 text-center text-amber-200"><Inbox className="w-10 h-10 mx-auto mb-3"/><h3 className="font-bold text-lg">No incoming mailbox is connected</h3><p className="text-sm mt-2 text-amber-200/75">Configure IMAP on an account first. ZeptoMail is send-only, so replies require a separate IMAP mailbox.</p></div></div>;

  return <div className="h-full min-h-[620px] flex flex-col bg-slate-950 text-slate-100">
    <header className="min-h-16 border-b border-slate-800 px-5 py-2 flex flex-wrap items-center gap-3 bg-slate-950/95">
      <div className="flex items-center gap-2 min-w-fit"><Mail className="w-5 h-5 text-amber-400"/><h2 className="font-bold text-lg">Mailbox</h2></div>
      <div className="relative min-w-[220px] max-w-xl flex-1 mx-auto"><Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500"/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search this inbox" className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-sm outline-none focus:border-amber-500/70"/></div>
      <select value={activeId} onChange={e=>setAccountId(e.target.value)} className="max-w-[250px] bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-sm outline-none">{capable.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select>
      <button onClick={()=>void refresh()} disabled={loading} title="Refresh inbox" className="p-2.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl disabled:opacity-50"><RefreshCw className={`w-4 h-4 ${loading?'animate-spin':''}`}/></button>
    </header>
    {error&&<div className="mx-5 mt-4 p-3 border border-rose-500/30 bg-rose-500/10 rounded-xl text-rose-300 text-sm">{error}</div>}
    <div className="flex-1 grid grid-cols-1 lg:grid-cols-[210px_minmax(340px,420px)_1fr] overflow-hidden">
      <aside className="hidden lg:flex flex-col border-r border-slate-800 p-3"><div className="flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl bg-amber-500/10 text-amber-300 font-semibold text-sm"><span className="flex items-center gap-3"><Inbox className="w-4 h-4"/>Inbox</span><span className="text-xs">{unreadCount}</span></div><div className="mt-auto border-t border-slate-800 pt-4 px-2 flex items-center gap-3"><div className="w-9 h-9 rounded-full bg-slate-800 grid place-items-center"><User className="w-4 h-4"/></div><div className="min-w-0"><div className="text-xs font-semibold truncate">{activeAccount?.name}</div><div className="text-[11px] text-slate-500 truncate">{(activeAccount as any)?.fromEmail}</div></div></div></aside>
      <section className={`${mobilePane==='message'?'hidden lg:flex':'flex'} flex-col border-r border-slate-800 min-h-0`}>
        <div className="h-14 px-3 border-b border-slate-800 flex items-center gap-2"><button onClick={toggleAll} title="Select all visible" className="p-2 hover:bg-slate-800 rounded-lg">{allVisibleSelected?<CheckSquare className="w-4 h-4 text-amber-400"/>:<Square className="w-4 h-4 text-slate-400"/>}</button><div className="h-5 w-px bg-slate-800"/><button onClick={()=>void bulk('read')} disabled={!selected.length} title="Mark read" className="p-2 hover:bg-slate-800 rounded-lg disabled:opacity-30"><MailOpen className="w-4 h-4"/></button><button onClick={()=>void bulk('unread')} disabled={!selected.length} title="Mark unread" className="p-2 hover:bg-slate-800 rounded-lg disabled:opacity-30"><Mail className="w-4 h-4"/></button><button onClick={()=>void bulk('delete')} disabled={!selected.length} title="Delete" className="p-2 hover:bg-rose-950 text-rose-400 rounded-lg disabled:opacity-30"><Trash2 className="w-4 h-4"/></button><span className="ml-auto text-xs text-slate-500">{selected.length?`${selected.length} selected`:`${filtered.length} messages`}</span></div>
        <div className="flex-1 overflow-y-auto">{filtered.map(m=>{const checked=selected.includes(m.uid);const active=String(preview?.uid||'')===m.uid;return <div key={m.uid} onClick={()=>void openMessage(m.uid)} className={`px-3 py-3.5 border-b border-slate-800/70 cursor-pointer ${active?'bg-slate-800':m.unread?'bg-amber-500/[0.06] hover:bg-slate-900':'hover:bg-slate-900/80'}`}><div className="flex gap-3"><input type="checkbox" checked={checked} onClick={e=>e.stopPropagation()} onChange={e=>setSelected(c=>e.target.checked?[...c,m.uid]:c.filter(id=>id!==m.uid))} className="mt-1 accent-amber-500"/><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><span className={`truncate text-sm ${m.unread?'font-bold':'font-medium text-slate-300'}`}>{m.from_name||m.from_email||'Unknown sender'}</span><span className="ml-auto text-[11px] text-slate-500 shrink-0">{formatDate(m.date)}</span></div><div className={`truncate text-sm mt-0.5 ${m.unread?'font-semibold text-slate-200':'text-slate-400'}`}>{m.subject||'(No subject)'}</div><div className="truncate text-[11px] text-slate-600 mt-1">{m.from_email}</div></div>{m.unread&&<span className="w-2 h-2 mt-2 rounded-full bg-amber-400 shrink-0"/>}</div></div>})}{!loading&&!filtered.length&&<div className="p-12 text-center text-slate-500"><Inbox className="w-9 h-9 mx-auto mb-3"/><p>{query?'No matching messages':'Your inbox is empty'}</p></div>}{loading&&!messages.length&&<div className="p-12 text-center text-slate-500"><RefreshCw className="w-7 h-7 mx-auto mb-3 animate-spin"/>Fetching incoming mail…</div>}</div>
      </section>
      <section className={`${mobilePane==='list'?'hidden lg:flex':'flex'} flex-col min-h-0 bg-slate-900/35`}>{previewLoading?<div className="flex-1 grid place-items-center text-slate-500"><RefreshCw className="w-7 h-7 animate-spin"/></div>:preview?<><div className="min-h-16 px-5 py-3 border-b border-slate-800 flex items-center gap-2"><button onClick={()=>setMobilePane('list')} className="lg:hidden p-2 hover:bg-slate-800 rounded-lg"><ChevronLeft className="w-5 h-5"/></button><button onClick={reply} className="px-3 py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-lg text-xs font-semibold flex items-center gap-2"><Reply className="w-4 h-4"/>Reply</button></div><article className="flex-1 overflow-y-auto p-6 lg:p-8"><h1 className="text-xl lg:text-2xl font-bold leading-snug">{preview.subject||'(No subject)'}</h1><div className="mt-6 flex items-start gap-3 border-b border-slate-800 pb-5"><div className="w-10 h-10 rounded-full bg-amber-500/15 text-amber-300 grid place-items-center font-bold">{(preview.from_name||preview.from_email||'?').charAt(0).toUpperCase()}</div><div className="min-w-0"><div className="font-semibold text-sm">{preview.from_name||preview.from_email}</div><div className="text-xs text-slate-500 break-all">&lt;{preview.from_email}&gt;</div><div className="text-xs text-slate-500 mt-1">To: {preview.to||(activeAccount as any)?.fromEmail}</div></div><time className="ml-auto text-xs text-slate-500 text-right">{preview.date}</time></div>{preview.html?<iframe title="Email message preview" sandbox="" referrerPolicy="no-referrer" srcDoc={safeHtmlDocument(preview.html)} className="mt-7 w-full min-h-[520px] rounded-xl border border-slate-800 bg-white"/>:<div className="mt-7 whitespace-pre-wrap break-words text-sm leading-7 text-slate-200">{preview.text||'This message has no displayable body.'}</div>}</article></>:<div className="flex-1 grid place-items-center text-center text-slate-500 p-8"><div><MailOpen className="w-12 h-12 mx-auto mb-4 text-slate-700"/><h3 className="font-semibold text-slate-400">Select a message to read</h3><p className="text-xs mt-2">Message content loads only when you open it.</p></div></div>}</section>
    </div>
  </div>;
};
