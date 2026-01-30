# Temporal MongoDB Tests - Proje Yol Haritası

## Mevcut Durum

### Tamamlanan

- ✅ Repo yapısı oluşturuldu (`sagdelen/temporal-mongodb-tests`)
- ✅ mise.toml ile tool/task management
- ✅ Docker compose: `temporal-mongodb-db`, `temporal-mongodb-server`, `temporal-mongodb-ui`
- ✅ Namespace: `temporal-mongodb`
- ✅ E2E testleri: 329 test, ~6 dakikada geçiyor
- ✅ Omes entegrasyonu: Çoğu senaryo çalışıyor
- ✅ Temel GitHub Actions workflow

### Çalışan Komutlar

```bash
mise run setup       # Infra + namespace + search attr
mise run tests       # 329 E2E test
mise run load        # Quick: 100 iter, 20 concurrent
mise run load:standard  # 500 + 1000 iter
mise run load:full   # Stress test dahil
mise run teardown    # Kapat
mise run clean       # Her şeyi temizle
```

---

## Omes Senaryo Test Sonuçları (2026-01-30)

| Senaryo                              | Durum      | Notlar                                                                                       |
| ------------------------------------ | ---------- | -------------------------------------------------------------------------------------------- |
| `workflow_with_single_noop_activity` | ✅ PASS    | 10 iter/0.2s                                                                                 |
| `workflow_with_many_actions`         | ⚠️ PARTIAL | `max-concurrent=1` ile OK, yüksek concurrency'de `ChildWorkflowExecutionAlreadyStartedError` |
| `workflow_on_many_task_queues`       | ✅ PASS    | `--option task-queue-count=N --task-queue-suffix-index-end N-1` gerekli                      |
| `throughput_stress`                  | ✅ PASS    | 3 iter/41s (child wf + continue-as-new)                                                      |
| `scheduler_stress`                   | ✅ PASS    | 2 iter/50s                                                                                   |
| `ebb_and_flow`                       | ✅ PASS    | `--duration` gerekli (iteration değil)                                                       |
| `fixed_resource_consumption`         | ✅ PASS    | 2m20s                                                                                        |
| `state_transitions_steady`           | ✅ PASS    | `--option state-transitions-per-second=N` gerekli                                            |
| `fuzzer`                             | ❌ SKIP    | Rust + protoc-gen-go setup gerekli (MongoDB ile ilgisiz)                                     |

### � ÇÖZÜLDÜ: `workflow_with_many_actions`

**Hata:** `ChildWorkflowExecutionAlreadyStartedError` (concurrent > 1)

**Sonuç:** Bu MongoDB'ye özgü bir bug **DEĞİL**!

PostgreSQL ile de aynı hata oluşuyor:

- MongoDB: `max-concurrent=1` ✅, `max-concurrent>1` ❌
- PostgreSQL: `max-concurrent=1` ✅, `max-concurrent>1` ❌

**Teşhis:** Senaryo tasarımında child workflow ID'leri concurrent iterasyonlarda çakışıyor. Bu omes senaryosunun bilinen bir limitasyonu.

**Aksiyon:** Aksiyona gerek yok - MongoDB persistence doğru çalışıyor.

---

## Faz 0: Benchmark Karşılaştırma (YENİ)

**Öncelik:** Yüksek  
**Tahmini Süre:** 4-6 saat

### Task 0.1: Upstream Benchmark Sonuçlarını Araştır

- [ ] Temporal'ın resmi benchmark sonuçlarını bul (varsa)
- [ ] Omes benchmark raporlarını incele
- [ ] PostgreSQL için baseline değerleri belirle

### Task 0.2: MongoDB vs PostgreSQL Karşılaştırma

**Eğer upstream sonuçları bulunamazsa:**

- [ ] Ayrı repo oluştur: `temporal-persistence-benchmark`
- [ ] Aynı donanımda her iki persistence'ı test et
- [ ] Senaryolar:
  - `workflow_with_single_noop_activity` (basit throughput)
  - `throughput_stress` (karmaşık workflow)
  - `scheduler_stress` (schedule performance)
- [ ] Metrikler:
  - Workflows/second
  - Latency (p50, p95, p99)
  - Resource usage (CPU, memory, disk I/O)

### Task 0.3: Sonuçları Dokümante Et

- [ ] Karşılaştırma tablosu oluştur
- [ ] Avantaj/dezavantaj analizi
- [ ] MongoDB optimization önerileri

---

## Faz 1: Omes Test Coverage Genişletme

**Öncelik:** Yüksek  
**Tahmini Süre:** 2-3 saat

### Task 1.1: Mevcut Omes Senaryolarını Analiz Et

**Dosya:** `omes/repo/scenarios/`

- [x] Her senaryo dosyasını oku ve ne test ettiğini dokümante et (yukarıdaki tablo)
- [x] MongoDB persistence için hangilerinin anlamlı olduğunu belirle

**Omes'teki senaryolar:**
| Senaryo | Dosya | Açıklama |
|---------|-------|----------|
| `workflow_with_single_noop_activity` | workflow_with_single_noop_activity.go | Tek activity, temel test |
| `workflow_with_many_actions` | workflow_with_many_actions.go | Çoklu child workflow + activity |
| `workflow_on_many_task_queues` | workflow_on_many_task_queues.go | Farklı task queue'lar |
| `throughput_stress` | throughput_stress.go | Sürekli yük testi |
| `scheduler_stress` | scheduler_stress.go | Schedule stresi |
| `ebb_and_flow` | ebb_and_flow.go | Yükün artıp azalması |
| `fixed_resource_consumption` | fixed_resource_consumption.go | Sabit kaynak tüketimi |
| `state_transitions_steady` | state_transitions_steady.go | State geçişleri |
| `fuzzer` | fuzzer.go | Fuzzy testing |

### Task 1.2: run-load.sh Güncelle

**Dosya:** `scripts/run-load.sh`

- [ ] `standard` moduna daha fazla senaryo ekle
- [ ] `full` modunu genişlet
- [ ] Her senaryo için uygun iteration/concurrency ayarla

**Önerilen güncelleme:**

```bash
# standard mode
run_scenario "workflow_with_single_noop_activity" 500 50
run_scenario "workflow_with_many_actions" 200 20
run_scenario "workflow_on_many_task_queues" 100 10

# full mode
run_scenario "workflow_with_single_noop_activity" 2000 100
run_scenario "workflow_with_many_actions" 500 50
run_scenario "throughput_stress" --duration 30m
run_scenario "ebb_and_flow" 1000 50
```

### Task 1.3: Yeni mise Task'ları Ekle

**Dosya:** `mise.toml`

- [ ] `load:scenario` task'ı ekle (tek senaryo çalıştır)
- [ ] `load:stress` task'ı ekle (sadece stress test)
- [ ] `test` alias'ı ekle (`tests`'e yönlendir)

---

## Faz 2: GitHub Actions İyileştirme

**Öncelik:** Yüksek  
**Tahmini Süre:** 2-3 saat

### Task 2.1: E2E Testleri Workflow'a Ekle

**Dosya:** `.github/workflows/load-test.yml`

- [ ] E2E testleri ayrı step olarak ekle
- [ ] Test sonuçlarını artifact olarak kaydet
- [ ] Test özeti oluştur

### Task 2.2: Matrix Build Ekle

**Dosya:** `.github/workflows/load-test.yml`

- [ ] Farklı MongoDB versiyonları (6.0, 7.0, 8.0)
- [ ] Farklı Temporal versiyonları test et

**Örnek matrix:**

```yaml
strategy:
  matrix:
    mongodb: ["6.0", "7.0", "8.0"]
    temporal: ["1.30.0", "1.29.0"]
```

### Task 2.3: Scheduled Workflow Ekle

**Dosya:** `.github/workflows/scheduled-tests.yml` (yeni)

- [ ] Haftalık otomatik test
- [ ] Sonuçları issue olarak raporla
- [ ] Badge ekle README'ye

### Task 2.4: PR Workflow Ekle

**Dosya:** `.github/workflows/pr-check.yml` (yeni)

- [ ] Her PR'da quick test çalıştır
- [ ] Lint/format kontrolü

---

## Faz 3: Test Coverage Analizi ve İyileştirme

**Öncelik:** Orta  
**Tahmini Süre:** 3-4 saat

### Task 3.1: E2E Test Kategorileri Analizi

**Dosya:** `tests/` altındaki tüm klasörler

- [ ] Her kategorideki test sayısını dokümante et
- [ ] Eksik coverage alanlarını belirle

**Mevcut kategoriler:**
| Kategori | Dosya Sayısı | Açıklama |
|----------|--------------|----------|
| activity | 3 | Activity testleri |
| batch | 1 | Batch operations |
| concurrency | 1 | Concurrent execution |
| context | 1 | Context propagation |
| core | 3 | Temel bağlantı/namespace |
| dataconverter | 1 | Data serialization |
| dataflow | 1 | ETL pattern |
| eagerwf | 1 | Eager workflow start |
| lifecycle | 1 | Workflow lifecycle |
| local_activities | 1 | Local activities |
| longrunning | 1 | Uzun workflow'lar |
| metadata | 1 | Metadata testleri |
| parallel | 1 | Parallel execution |
| persistence | 1 | Persistence testleri |
| retry | 2 | Retry policy |
| saga | 1 | Saga pattern |
| schedule | 1 | Scheduled workflows |
| search | 1 | Search attributes |
| signal | 3 | Signal testleri |
| taskqueue | 1 | Task queue testleri |
| timeout | 1 | Timeout testleri |
| timer | 1 | Timer testleri |
| update | 2 | Workflow update |
| visibility | 2 | Visibility query |
| workflow | 3 | Workflow testleri |

### Task 3.2: Eksik Test Alanları

- [ ] Nexus integration testleri
- [ ] Multi-cluster testleri (varsa)
- [ ] Large payload testleri
- [ ] High cardinality search attribute testleri

### Task 3.3: Test Performans Optimizasyonu

- [ ] Paralel test execution
- [ ] Test isolation kontrolü
- [ ] Slow test'leri işaretle

---

## Faz 4: Dokümantasyon

**Öncelik:** Orta  
**Tahmini Süre:** 1-2 saat

### Task 4.1: README Güncelle

**Dosya:** `README.md`

- [ ] Tüm mise komutlarını dokümante et
- [ ] Test kategorilerini açıkla
- [ ] Local development guide ekle

### Task 4.2: CONTRIBUTING.md Oluştur

**Dosya:** `CONTRIBUTING.md` (yeni)

- [ ] Yeni test ekleme rehberi
- [ ] Code style guide
- [ ] PR süreci

### Task 4.3: Test Sonuç Raporlama

- [ ] Test coverage badge
- [ ] Son test sonuçları badge
- [ ] COMPATIBILITY.md güncelle

---

## Faz 5: İleri Düzey Özellikler

**Öncelik:** Düşük  
**Tahmini Süre:** 4-6 saat

### Task 5.1: Metrics Collection

- [ ] Prometheus metrics ekle
- [ ] Grafana dashboard
- [ ] Performance trend tracking

### Task 5.2: Chaos Testing

- [ ] MongoDB replica set failover testi
- [ ] Network partition testi
- [ ] Container restart testi

### Task 5.3: Benchmark Suite

- [ ] Standart benchmark senaryoları
- [ ] PostgreSQL/MySQL ile karşılaştırma
- [ ] Sonuçları dokümante et

---

## Hızlı Referans: Dosya Değişiklikleri

### Faz 1 Dosyaları

```
scripts/run-load.sh       # Senaryo güncellemeleri
mise.toml                 # Yeni task'lar
```

### Faz 2 Dosyaları

```
.github/workflows/load-test.yml      # Güncelle
.github/workflows/scheduled-tests.yml # Yeni
.github/workflows/pr-check.yml        # Yeni
```

### Faz 3 Dosyaları

```
tests/**/*.py             # Test iyileştirmeleri
tests/conftest.py         # Shared fixtures
```

### Faz 4 Dosyaları

```
README.md
CONTRIBUTING.md           # Yeni
COMPATIBILITY.md          # Güncelle
```

---

## Öncelik Sırası (Önerilen)

1. **Faz 1** - Omes genişletme (esas değer burada)
2. **Faz 2** - GitHub Actions (otomasyon)
3. **Faz 4** - Dokümantasyon (kullanılabilirlik)
4. **Faz 3** - Test coverage (kalite)
5. **Faz 5** - İleri özellikler (nice-to-have)

---

## Notlar

- Her task bağımsız çalışabilir şekilde tasarlandı
- Tahmini süreler tek başına çalışma için
- Faz 1 ve 2 paralel yapılabilir
- Düşük maliyetli modeller için task'lar küçük tutuldu
