# 🎨 CertifyHub — Frontend Architecture & Developer Guide

A production-quality Single Page Application (SPA) dashboard for **CertifyHub**, built with **HTML5**, **Tailwind CSS**, **Alpine.js**, and **Lucide Icons**, inspired by **Preline** and **Flowbite** enterprise design systems.

---

## 📁 Directory Structure

```text
frontend/
├── public/
│   └── index.html      # Complete Single Page Application (UI + Reactive Logic)
└── README.md           # This documentation
```

---

## 🛠️ Technology Stack & Rationale

| Tool | Purpose | Why It Was Chosen |
|---|---|---|
| **Alpine.js 3.x** | Reactive State Management | Provides full two-way binding (`x-model`), loops (`x-for`), conditional rendering (`x-show`), and lifecycle hooks (`x-init`) directly in HTML without the overhead of Webpack/Vite or heavy `node_modules` bundles. |
| **Tailwind CSS (CDN)** | Utility-First Styling System | Delivers a clean, enterprise aesthetic with custom design tokens, accessible color contrasts, responsive breakpoints, and glassmorphism backdrops. |
| **Lucide Icons** | SVG Icon System | Clean, modern vector icons dynamically rendered via `lucide.createIcons()`. |
| **Inter & JetBrains Mono** | Typography | Professional sans-serif for UI elements and monospace for UUIDs and API timestamps. |

---

## 🎨 Design System & Color Palette

The interface follows a clean enterprise SaaS light-mode design system:

- **Background Canvas**: `#F8FAFC` (`bg-slate-50`)
- **Card Surfaces**: Pure White `#FFFFFF` (`bg-white`) with subtle borders `#E2E8F0` (`border-slate-200`)
- **Primary Accent**: Refined Indigo `#4F46E5` (`text-brand-600` / `bg-brand-600`) with hover `#4338CA`
- **Primary Typography**: Deep Slate `#0F172A` (`text-slate-900`)
- **Secondary Typography**: Slate Gray `#64748B` (`text-slate-500`)
- **Status Badges (Flowbite Style)**:
  - **`pending`**: Amber tint (`bg-amber-50 text-amber-700 border-amber-200`)
  - **`processing` / `generating`**: Blue tint with animated pulse (`bg-blue-50 text-blue-700 border-blue-200`)
  - **`completed`**: Emerald tint (`bg-emerald-50 text-emerald-700 border-emerald-200`)
  - **`partially_completed`**: Indigo/Violet tint (`bg-indigo-50 text-indigo-700 border-indigo-200`)
  - **`failed`**: Rose tint (`bg-rose-50 text-rose-700 border-rose-200`)

---

## 🌟 Application Views & Capabilities

### 1. Overview Dashboard (`overview`)
- **Executive Metric Cards**: Real-time aggregation of Total Recipients, Completed Certificates, Active Jobs, and Failed Records.
- **Recent Batches Activity**: Summary table of recently submitted jobs with status pills and 1-click tracking.
- **Vector Template Showcase**: High-fidelity visual mockup of the ReportLab A4 landscape certificate with gold borders, signatures, and UUID watermark.

### 2. Create Batch Console (`create`)
- **Event & Issuer Form**: Organization name and course/event title inputs.
- **Dynamic Recipient Row Manager**:
  - Add or remove recipient rows with live row counter.
  - Fields: Full Name, Email Address, Specialization (optional), and Completion Date (optional).
  - Desktop compact table layout / Mobile stacked card layout.
- **1-Click "Load Sample (5 Recipients)"**: Instantly populates realistic batch data for testing.
- **Smart Validation**: Inline required checks, email regex format validation, and client-side duplicate email warning.
- **Loading State**: Animated spinner during background task dispatch.

### 3. Live Job Progress Tracker (`tracker`)
- **Real-Time Polling**: Strictly preserves the **1.5-second polling interval** querying `GET /api/v1/jobs/{id}/detail`.
- **Live Progress Bar**: Dynamic percentage indicator (`0%` to `100%`) reflecting Celery worker progress.
- **Terminal State Cleanup**: Automatically halts polling once the job finishes (`completed`, `partially_completed`, `failed`).
- **Recipient Status Table**: Per-recipient status badge and direct **"Download PDF"** buttons.
- **Failure Diagnostics**: Expandable error message captures for any failed records.

### 4. Jobs History (`history`)
- Session history of all batch UUIDs stored in browser `localStorage`.
- Direct "Track" navigation to inspect any past job.
- Option to clear local session history.

### 5. Certificates & Downloads Repository (`downloads`)
- Aggregated repository of all generated certificates.
- Live search/filter by recipient name, email, or event title.
- Direct PDF download buttons.

### 6. Toast Notification System
- Floating alert toasts for submission confirmations, clipboard copy events, and validation alerts with auto-dismiss timers.

### 7. Job UUID Lookup Modal
- Quick-search modal accessible from the top header to paste any external Job UUID and track it immediately.

---

## ⚡ Alpine.js Reactive State Machine

All application logic is encapsulated inside the `certifyApp()` component:

```javascript
function certifyApp() {
  return {
    activeTab: 'overview',        // Current active view
    mobileSidebarOpen: false,     // Responsive drawer toggle
    openLookupModal: false,       // UUID search modal toggle
    currentJob: null,             // Active job detail object
    savedJobs: [],                // Array of jobs persisted in localStorage
    pollTimer: null,              // 1.5s polling interval handle
    isSubmitting: false,          // Form submission loading flag
    isPollingRequest: false,      // Active network request flag
    engineHealthy: true,          // Backend health check status

    // Methods
    initApp(),                    // Loads localStorage, runs /health check, renders icons
    setTab(tab),                  // Switches view and refreshes icons
    addRecipient(),               // Appends blank recipient row
    removeRecipient(idx),         // Removes recipient at index
    loadSampleData(),             // Fills 5 valid test recipients
    submitJob(),                  // POSTs to /api/v1/jobs/, saves to history, starts tracking
    trackJob(jobId),              // Sets up 1.5s polling loop for GET /api/v1/jobs/{id}/detail
    fetchJobStatus(),             // Performs single GET request and updates state
    addToast(type, message),      // Dispatches floating toast notification
    
    // Computed Getters
    get totalRecipientsCount(),   // Aggregated recipients across all jobs
    get completedCertsCount(),    // Aggregated completed certificates
    get activeJobsCount(),        // Count of pending/processing jobs
    get filteredCertificates()    // Filtered certificates for Downloads tab
  };
}
```

---

## 🔌 API Integration Mapping

| Action in UI | HTTP Method | Endpoint | Response Handled |
|---|---|---|---|
| **Health Check** | `GET` | `/health` | Updates sidebar engine operational pill |
| **Submit Batch** | `POST` | `/api/v1/jobs/` | Receives `202 Accepted` + `job_id`, begins tracking |
| **Poll Job Progress** | `GET` | `/api/v1/jobs/{id}/detail` | Updates progress %, counters, and recipient statuses |
| **Download PDF** | `GET` | `/api/v1/jobs/{id}/certificates/{cert_id}/download` | Streams raw PDF binary file to browser |

---

## 📱 Responsive Breakpoints

- **Desktop (`lg` / 1024px+)**: Fixed left sidebar (`w-64`), multi-column metric grids, inline recipient table rows.
- **Tablet (`md` / 768px - 1023px)**: Adaptive 2-column cards, flexible form inputs.
- **Mobile (`< 768px`)**: Collapsible slide-over drawer with backdrop blur, stacked recipient cards, and compact action buttons.
