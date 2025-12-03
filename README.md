# 📘 LLM Tabanlı Akıllı Analitik Asistanı

**Contoso Retail Data Warehouse için Doğal Dil → SQL → İş Analitiği Dönüşümü**

Bu proje kapsamında, doğal dilde sorulan iş sorularının otomatik olarak SQL sorgularına dönüştürüldüğü, çalıştırıldığı ve sonuçların iş odaklı bir özet halinde sunulduğu bir akıllı analitik sistemi oluşturulmuştur. Sistem, LLM destekli bir mimari üzerine inşa edilmiştir ve Microsoft Contoso Retail veri ambarı üzerinde çalışacak şekilde tasarlanmıştır.

---

## 📌 1. Proje Amacı

Projenin amacı, kullanıcıdan gelen doğal dildeki iş sorularının:

1. **Anlaşılması**,
2. **Uygun SQL sorgusuna dönüştürülmesi**,
3. **Veritabanı üzerinde çalıştırılması**,
4. **Sonuçların iş perspektifiyle yorumlanması**,
5. **Gerekirse grafikle görselleştirilmesi**

süreçlerini uçtan uca otomatikleştiren bir analitik asistanın oluşturulmasıdır.

---

## 🧠 2. Ana Özellikler

### ✔️ Doğal Dil → SQL Dönüşümü

* Soru niyeti (intent) otomatik olarak sınıflandırılmaktadır.
* Gerekli tablolar, kolonlar ve ilişkiler dinamik olarak belirlenmektedir.
* SQL sorguları LLM tarafından oluşturulmakta, temizlenmekte ve doğrulanmaktadır.

### ✔️ Dinamik Şema Algılama

* Veritabanı şeması *INFORMATION_SCHEMA* üzerinden gerçek zamanlı okunmaktadır.
* Yabancı anahtar ilişkileri çıkarılmakta ve modele bağlam (context) olarak sunulmaktadır.

### ✔️ Template Engine

* En sık karşılaşılan iş soruları için (toplam satış, en çok satan ürün vb.) güvenilir SQL şablonları kullanılmaktadır.
* Hatalı SQL üretimini azaltmak amacıyla LLM öncesi kural tabanlı çözüm uygulanmaktadır.

### ✔️ SQL Normalizasyonu & Doğrulama

* Üretilen SQL sorguları otomatik normalizasyon sürecinden geçirilmektedir.
* Eksik JOIN, yanlış kolon adı, ORDER BY hatası vb. durumlar otomatik olarak tespit edilmektedir.

### ✔️ Self-Correction Pipeline

* Hatalı SQL tespit edildiğinde sistem, modeli otomatik olarak düzeltme moduna almaktadır.
* Yeni SQL oluşturularak doğrulanmakta ve kullanıcıya yalnızca geçerli sürüm sunulmaktadır.

### ✔️ Sonuç Analizi (Executive Summary)

* SQL çalıştırıldıktan sonra LLM tarafından iş odaklı özet oluşturulmaktadır.
* Yönetici seviyesinde yorum, trend, karşılaştırma ve çıkarımlar eklenmektedir.

### ✔️ Web Arayüzü (Streamlit)

* Soru sorma, üretilen SQL’i görüntüleme, tablo gösterimi ve grafikler için modern bir arayüz sağlanmaktadır.
* Sorgu geçmişi ve desen keşif modülü sunulmaktadır.

---

## 🏗️ 3. Sistem Mimarisi

Proje, aşağıdaki ana bileşenlerden oluşacak şekilde tasarlanmıştır:

### 🔹 **1. Intent Classifier (Niyet Sınıflandırma Modülü)**

* Sorgunun türü belirlenmektedir: *aggregation, ranking, comparison, trend, anomaly detection…*
* Sorgunun karmaşıklığı tahmin edilmektedir.
* Kullanılması gereken tablolar çıkarılmaktadır.

### 🔹 **2. SQL Generator (LLM Pipeline + Template Engine)**

* Template Engine → En güvenilir hızlı üretim
* LLM SQL Generator → Şablon bulunamazsa devreye giren esnek üretim
* SQL Extractor → EXPLANATION kısımları ayrılmakta, sadece SQL alınmaktadır.
* SQL Validator → Sorgu yürütülmeden önce kontrol yapılmaktadır.

### 🔹 **3. Database Access Layer**

* Microsoft SQL Server / ContosoRetailDW bağlantısı yapılmaktadır.
* Güvenli sorgu çalıştırma mekanizması uygulanmaktadır.

### 🔹 **4. Summary Generator**

* Yönetici özetleri (executive summary) üretmektedir.
* Performans ve trend analizleri oluşturulmaktadır.

### 🔹 **5. Web UI (Streamlit)**

* Chat arayüzü
* Sonuç görselleştirme
* Sorgu geçmişi
* Desen madenciliği (Pattern Miner)

---

## 🗂️ 4. Proje Klasör Yapısı

```
├── app
│   ├── core
│   │   ├── intent_classifier.py
│   │   ├── schema_builder.py
│   ├── llm
│   │   ├── sql_generator.py
│   │   ├── prompt_manager.py
│   │   ├── templates.py
│   ├── database
│   │   ├── db_client.py
│   │   ├── query_validator.py
│   │   ├── sql_normalizer.py
│   ├── memory
│   │   ├── query_logger.py
│   │   ├── pattern_miner.py
│   ├── utils
│       ├── logger.py
│
├── tests
│   ├── run_test_scenarios.py
│   ├── test_scenarios.json
│
├── poc_streamlit.py
├── poc_interactive.py
├── README.md
```

---

## ⚙️ 5. Kurulum ve Çalıştırma

### **1️⃣ Gerekli Paketler Kurulur**

```bash
pip install -r requirements.txt
```

### **2️⃣ Ollama Modelinin Yüklenmesi**

```bash
ollama pull llama3.1:8b
```

### **3️⃣ Veritabanı Bağlantısı Ayarlanır**

`config.py` içinde SQL Server bilgileri düzenlenmektedir.

### **4️⃣ Web Arayüzünün Başlatılması**

```bash
streamlit run poc_streamlit.py
```

### **5️⃣ Terminal Üzerinden Soru Sorma**

```bash
python -c "from app.llm.sql_generator import DynamicSQLGenerator; print(DynamicSQLGenerator().generate_sql('2008 yılında toplam satış nedir?'))"
```

---

## 🧪 6. Test Senaryoları

Testler `tests/run_test_scenarios.py` çalıştırılarak uygulanmaktadır:

```bash
python tests/run_test_scenarios.py
```

Testler şunları kapsamaktadır:

* Doğru intent sınıflandırması
* Template Engine doğruluğu
* SQL üretimi ve doğrulama
* Hatalı SQL düzeltme pipeline’ı
* Sonuç özetleme tutarlılığı

---

## 📈 7. Örnek Sorgular

Aşağıdaki sorular sistem tarafından başarıyla çalıştırılabilmektedir:

| Soru                                          | Açıklama                    |
| --------------------------------------------- | --------------------------- |
| “2008 yılında toplam satış nedir?”            | Aggregation                 |
| “En çok satan 5 ürün hangisi?”                | Ranking                     |
| “2007 mağaza vs online satış karşılaştırması” | Comparison                  |
| “2009 aylık satış trendi”                     | Time-series                 |
| “En az satan ürün hangisi?”                   | Ranking (template fallback) |

---

## 🚀 8. Yol Haritası (Future Work)

| Özellik                       | Durum                  |
| ----------------------------- | ---------------------- |
| Gelişmiş grafik motoru        | Planlandı              |
| GPT-4o Mini fallback          | Entegrasyon aşamasında |
| Multi-agent SQL planner       | Planlanıyor            |
| Fine-tuning (Contoso’ya özel) | Araştırma aşamasında   |

---

## 📝 9. Lisans

Bu proje araştırma ve geliştirme amaçlı oluşturulmuş olup ticari kullanım için uygun olmayabilir.

---

