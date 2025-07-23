## Async Image Loading Optimization

### ✅ **Cache Optimization Complete!**
The `fetch_image_data()` method now returns cached images **immediately** without network requests. Only cache misses require network calls.

### Current Performance
- **Cache Hits**: Instant display (no network delay) ⚡
- **Cache Misses**: 5-second UI blocking during network request ❌

### Simplified Architecture
```
UI Request → fetch_image_data()
             ├─ Cache Hit → Return immediately (instant) ✅
             └─ Cache Miss → HTTP request (blocks UI) ❌ → Wrap in thread
```

### Revised Implementation Plan

#### **Phase 1: Frontend Threading (Simple & Effective)**
- [x] Create async wrapper for `load_component_image_new()`
- [x] Add placeholder display during loading ("Loading..." text)
- [x] Use `threading.Thread` for network requests only
- [x] Use `root.after()` for thread-safe UI updates
- [x] Handle loading/error states in UI

#### **Phase 2: UX Enhancements**
- [ ] Implement graceful error states with retry options
- [ ] Add request cancellation on view changes
- [ ] Preload images for search results in background

#### **Phase 3: Performance Monitoring**
- [ ] Add metrics for cache hit/miss rates
- [ ] Monitor network request patterns
- [ ] Optimize cache warming strategies

### Implementation Focus
**Primary**: Thread wrap the existing `fetch_image_data()` calls in frontend
**Secondary**: Enhanced UX with loading states and error handling  
**Future**: Advanced optimizations based on usage patterns

## Feature Name
- [x] Get Image Loading Working (replaced by async optimization above)
- [ ] Digikey Order Scan
- [ ] Bug Fixes
    - [x] barcode low stock entry enter not working
    - [ ] Backup creates 2 backups/ prints backup msg twice
    - [ ] Bulk entry
        - [ ] Things dont light up

## request_media
- [x] set up prebuild binary as venv source for my local development
- [x] format headers and param correctly
- [x] extract the model from digikey
- [x] dl the image from the supplied link
- [x] create a database and cash the image blob
