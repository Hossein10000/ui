# AgentHost UI — تقرير Discovery والتنفيذ

**التاريخ:** 2026-07-24  
**النطاق:** `https://agenthost.tech/ui/`  
**الحالة:** Vertical Slice منفّذ ومتحقق

## الملخص التنفيذي

الموقع الحالي ليس نموذجاً وهمياً بالكامل: هو مستودع GitHub فعلي وحاوية Python عاملة خلف Traefik وAuthelia. الشات متصل فعلياً بـ Hermes، وصندوق الوارد يقرأ نتائج وملفات حقيقية من التخزين المشترك.

تم اختيار Minimal Integration لأن البيئة الحالية لا تثبت الحاجة إلى قاعدة Graph أو Queue أو Workflow Service جديدة. أما Obsidian المربوط فعلياً بـ Hermes فـVault الخاص به فارغ حالياً؛ لذلك لم يتم إنشاء Graph تجميلي أو بيانات Mock.

## خريطة البنية الفعلية

| المجال | النتيجة المؤكدة |
|---|---|
| Repository | `Hossein10000/ui`، الفرع `main` |
| كود الموقع | `/root/ui` |
| الحاوية | `ui-ui-dashboard-1`، Python 3.12 |
| المسار العام | `agenthost.tech/ui` و`ui.agenthost.tech` |
| الحماية | Traefik HTTPS + Authelia |
| شبكة UI | `traefik_default` |
| Hermes | `hermes-agent-8yvs-hermes-agent-1` عبر API داخلي على 8642 |
| Inbox | JSON وملفات داخل `results-data` |
| Obsidian الفعلي | `/root/obsidian-vault`، عدد الملفات حالياً صفر |
| GitHub Projects | `ui`، `UI Design for agenthost.tech`، `ui-test-shim`، `Hermes Server Engineering` |

## تدفق البيانات الحالي

```text
Browser
  → Traefik + Authelia
  → ui-dashboard
  → Hermes Session API للشات
  → results-data للنتائج والملفات
```

## الخدمات المثبتة فعلياً

Hermes Agent، Hermes WebUI، UI Dashboard، FreeLLM API، Local Model Gateway، Honcho، Qdrant، SearXNG، Traefik، Authelia، Redis، PostgreSQL.

وجود الحاوية لا يعني أن كل خدمة مرتبطة بالواجهة؛ تم التمييز بين الخدمات العاملة والخدمات المتصلة فعلياً بالـUI.

## الفجوات المؤكدة

1. لا توجد طبقة Workflow API دائمة ومثبتة للواجهة الحالية.
2. لا توجد Graph Database أو Graph Projection موثقة كمصدر حقيقة.
3. Vault Obsidian الفعلي فارغ، لذلك لا توجد علاقات أو Backlinks حقيقية لعرضها.
4. Inbox حقيقي لكنه يحتاج عقد provenance موحداً.
5. فتح الملفات موجود عبر روابط same-origin، لكن لا توجد طبقة Preview متخصصة.
6. توجد تغييرات سابقة غير ملتزمة في مستودع UI؛ لم يتم حذفها أو الكتابة فوقها.

## البدائل المعمارية

### Minimal Integration — المختار

إعادة استخدام Python UI وHermes وresults-data وTraefik وAuthelia. إضافة provenance وواجهات مصدر/حالة وGraph آمن يعرض UNAVAILABLE عند غياب المصدر.

**المزايا:** أقل مخاطرة، لا قاعدة جديدة، Rollback بسيط، لا تغيير في Hermes.  
**الحد:** لا يمكن إظهار Graph حقيقي قبل توفر ملاحظات Obsidian.

### Balanced Architecture

إضافة API منظم للـArtifacts والـWorkflow Runs وطبقة Adapters لـHermes وObsidian، مع استخدام التخزين الحالي أولاً ثم PostgreSQL عند إثبات الحاجة.

**المزايا:** قابلية توسع أفضل.  
**الحد:** خدمة وصيانة إضافية غير مبررة بعد بحجم البيانات الحالي.

### Full Personal AI OS

إضافة Workflow Engine وEvent Bus وGraph Projection وفهرسة دلالية وخدمات مستقلة.

**القرار:** مرفوض حالياً بسبب زيادة التعقيد والهجوم التشغيلي، وغياب بيانات Obsidian فعلية.

## ما تم تنفيذه

تم تعديل UI فقط وإضافة:

- حقول `source_type` و`source_id` و`last_verified_at` و`health_state` و`data_origin` لكل Inbox item.
- `GET /api/system/overview` لعرض مصادر النظام وحالتها.
- `GET /api/knowledge/graph` لإرجاع Graph فارغ موصوف صراحةً بـ`UNAVAILABLE` عند غياب Vault.
- توثيق Discovery وقرارات المعمارية.

## الاختبارات

| الاختبار | النتيجة |
|---|---|
| Python compile | PASS |
| Docker Compose validation | PASS |
| `git diff --check` | PASS |
| UI `/health` | HTTP 200 |
| `/api/system/overview` | HTTP 200 |
| `/api/knowledge/graph` | HTTP 200، دون بيانات مصطنعة |
| `/api/inbox` | HTTP 200، بيانات نتائج فعلية |
| Hermes restart | لم يُنفذ |
| Qdrant/Honcho/Local Gateway | لم تتغير |
| UI restart count | 0 بعد التشغيل |

## الوضع الأمني والتشغيلي

- لم يتم فتح منفذ عام جديد.
- لم يتم تغيير DNS أوSSH أوUFW.
- لم يتم حذف Volume أوRepository أوبيانات.
- لم تتم إعادة تشغيل Hermes أوQdrant أوHoncho أوLocal Gateway.
- بقيت المصادقة عبر Authelia.
- لم تُضمّن أسرار أوTokens في هذا التقرير.

## توصية المرحلة التالية

قبل بناء Graph أو Workflow Engine، يجب أولاً اتخاذ قرار مصدر المعرفة: تعبئة Vault `/root/obsidian-vault` ببيانات حقيقية أو توفير Adapter read-only معتمد. بعدها يمكن بناء استخراج الروابط والـBacklinks والـLocal Graph من المصدر الفعلي، مع provenance لكل عقدة وعلاقة.

## الملفات المرجعية

- `docs/DISCOVERY.md`
- `docs/ADR-0001-minimal-integration.md`
- `docs/ADR-0002-knowledge-provenance.md`
- `docs/VERTICAL-SLICE-2026-07-24.md`
