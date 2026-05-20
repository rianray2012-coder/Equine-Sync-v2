import React, { useEffect, useRef, useState } from "react";
import { api, fmtTime, fmtDate } from "../lib/api";
import { Bell, CheckCheck, Inbox } from "lucide-react";
import { Link } from "react-router-dom";

export default function NotificationsBell() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState({ items: [], unread: 0 });
  const ref = useRef(null);

  const refresh = () => {
    api.get("/notifications?limit=25")
      .then((r) => setData(r.data))
      .catch(() => {});
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, []);

  // close on outside click
  useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const markAll = async () => {
    try {
      await api.post("/notifications/read-all");
      refresh();
    } catch (err) {
      console.warn("[notifications] mark-all failed", err);
    }
  };

  const markOne = async (id) => {
    try {
      await api.post(`/notifications/${id}/read`);
      refresh();
    } catch (err) {
      console.warn("[notifications] mark-one failed", err);
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        data-testid="notifications-btn"
        onClick={() => setOpen((v) => !v)}
        aria-label="Notifications"
        className="p-2 rounded-lg hover:bg-equine-soft relative transition-colors"
      >
        <Bell strokeWidth={1.5} className="w-[18px] h-[18px]" />
        {data.unread > 0 && (
          <span
            data-testid="notifications-unread-dot"
            className="absolute top-1 right-1 min-w-[16px] h-[16px] px-1 rounded-full bg-equine-clay text-white text-[9.5px] font-semibold flex items-center justify-center"
          >
            {data.unread > 9 ? "9+" : data.unread}
          </span>
        )}
      </button>

      {open && (
        <div
          data-testid="notifications-panel"
          className="absolute right-0 mt-2 w-[360px] max-w-[92vw] bg-equine-card border border-equine-hairline rounded-2xl shadow-2xl z-50 overflow-hidden"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-equine-hairline">
            <div className="flex items-center gap-2">
              <Inbox className="w-3.5 h-3.5 text-equine-inkSoft" />
              <span className="text-[12px] uppercase tracking-[0.22em] text-equine-inkMuted font-semibold">
                Inbox
              </span>
            </div>
            <div className="flex items-center gap-2">
              {data.unread > 0 && (
                <button
                  data-testid="notifications-mark-all"
                  onClick={markAll}
                  className="text-[11.5px] text-equine-navy hover:underline inline-flex items-center gap-1"
                >
                  <CheckCheck className="w-3 h-3" /> Mark all read
                </button>
              )}
            </div>
          </div>
          <div className="max-h-[420px] overflow-y-auto scrollbar-luxe">
            {data.items.length === 0 ? (
              <div className="py-10 text-center text-[12.5px] text-equine-inkSoft">
                A quiet inbox. We'll let you know.
              </div>
            ) : (
              data.items.map((n) => (
                <button
                  key={n.id}
                  onClick={() => markOne(n.id)}
                  data-testid={`notification-${n.id}`}
                  className={`w-full text-left px-4 py-3 hairline hover:bg-equine-soft/60 transition-colors ${
                    !n.read_at ? "bg-equine-brass/5" : ""
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {!n.read_at && (
                      <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-equine-brassLight flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="text-[13px] text-equine-ink leading-snug">{n.summary}</div>
                      <div className="text-[11px] text-equine-inkSoft mt-1">
                        {fmtDate(n.occurred_at)} · {fmtTime(n.occurred_at)}
                      </div>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
          <div className="px-4 py-2.5 border-t border-equine-hairline text-right">
            <Link
              to="/settings"
              onClick={() => setOpen(false)}
              className="text-[11.5px] text-equine-inkMuted hover:text-equine-navy"
            >
              Notification preferences →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
