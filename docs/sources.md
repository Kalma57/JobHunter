# מקורות — מה תתי-הסוכנים מאזינים לו

(אושר 09/10/2026. להוספת מקור — שורה חדשה בטבלה, בלי לשנות קוד.)

## איך מחפשים בכל מקור
- **משתמשים בחיפוש ובסינון של האתר עצמו** (מילת חיפוש, ישראל, אזור) — לא מושכים את כל המשרות.
- מילות חיפוש מתוך [`search.md`](search.md): `Student`, `Intern`, `סטודנט` (ועוד אם יתברר שחסר).
- **רשת ביטחון:** פעם בשבוע סריקה מלאה בלי פילטר (קוד בלבד, לא משתמש ב-Pro) — כדי לתפוס משרות שהפילטר פספס (למשל "Early Career").
- הפילטרים של כל אתר נבחרים ע"י המוח **פעם אחת** (בהקמה או כשמשנים את `search.md`) ומוצגים למשתמש לאישור.

## אתרי חיפוש משרות — 3 סוכנים (סוכן לכל אתר)
| # | אתר | הערות |
|---|---|---|
| 1 | HireMeTech (juniors.hiremetech.com) | גם קבוצות הוואטסאפ מפנות לכאן |
| 2 | SecretHunter (secrethunter.io) | |
| 3 | Glassdoor | |

## חברות — 39 (שלוש שכבות, ראה למטה)
מערכת הגיוס של כל חברה תזוהה בשלב 8 (בדיקת קריאה בלבד). העמודה "סוג" מסמנת חברות השמה/מיקור חוץ — מפרסמות משרות בשם חברות אחרות, נשמרות לבקשת המשתמש.

| # | חברה | משרות (מקור: פוסט, 10/2026) | סוג |
|---|---|---|---|
| 1 | Elbit Systems | 573 | |
| 2 | IAI - Israel Aerospace Industries | 516 | |
| 3 | Matrix | 476 | השמה / מיקור חוץ |
| 4 | NVIDIA | 409 | |
| 5 | Rafael Advanced Defense Systems | 363 | |
| 6 | Ness Technologies | 225 | השמה / מיקור חוץ |
| 7 | Check Point Software | 163 | |
| 8 | ONE Technologies | 156 | השמה / מיקור חוץ |
| 9 | Mobileye | 150 | |
| 10 | GAV Systems Group | 115 | השמה / מיקור חוץ |
| 11 | Apple | 104 | |
| 12 | Google | 103 | |
| 13 | Deloitte | 97 | |
| 14 | Palo Alto Networks | 94 | |
| 15 | KLA | 89 | |
| 16 | abra | 78 | השמה / מיקור חוץ |
| 17 | Applied Materials | 63 | |
| 18 | SolarEdge Technologies | 62 | |
| 19 | Amazon (כולל Annapurna Labs, 108) | 59 + 108 | אותו אתר משרות — amazon.jobs |
| 20 | ScaleOps | 53 | |
| 21 | CyberArk | 52 | |
| 22 | QualityAI | 52 | |
| 23 | Oracle | 49 | |
| 24 | Qualcomm | 45 | |
| 25 | DRS RADA Technologies | 45 | |
| 26 | Commit | 44 | השמה / מיקור חוץ |
| 27 | Nebius | 44 | |
| 28 | monday.com | 43 | |
| 29 | Aman Group | 42 | השמה / מיקור חוץ |
| 30 | G-STAT | 40 | השמה / מיקור חוץ |
| 31 | Experis | 40 | השמה / מיקור חוץ |
| 32 | Nova Ltd | 38 | |
| 33 | HiBob | 37 | |
| 34 | Wix | 36 | |
| 35 | Bynet Data Communications | 35 | השמה / מיקור חוץ |
| 36 | Microsoft | 35 | |
| 37 | DriveNets | 34 | |
| 38 | Cato Networks | 34 | |
| 39 | Teva Pharmaceuticals | 33 | |

## זיהוי מערכות הגיוס (שלב 8, צעד 1 — הושלם, 10/10/2026)

כל 39 החברות נבדקו (קריאה בלבד). השכבות **אושרו ע"י המשתמש** (10/10/2026).

### שכבה 1 — מערכות ציבוריות (סוכן אחד לכל מערכת, קוד בלבד, נבנים ראשונים)

| מערכת | חברות | איך קוראים |
|---|---|---|
| Greenhouse | Nebius (42 בישראל), ScaleOps (32), Cato Networks (34) | GET `https://boards-api.greenhouse.io/v1/boards/<slug>/jobs` — slugs: `nebius`, `scaleops`, `catonetworks` |
| Lever (EU) | Mobileye (160 בישראל) | GET `https://api.eu.lever.co/v0/postings/mobileye?mode=json` |
| Workday | NVIDIA, KLA, Applied Materials | POST `https://<host>/wday/cxs/<tenant>/<site>/jobs` עם `{"appliedFacets":{},"limit":20,"offset":0,"searchText":"..."}` — `nvidia.wd5.myworkdayjobs.com/nvidia/NVIDIAExternalCareerSite`, `kla.wd1.myworkdayjobs.com/kla/Search`, `amat.wd1.myworkdayjobs.com/amat/External` |
| Eightfold (**חדש**) | Qualcomm (37 בישראל), Teva (35 בישראל) | Qualcomm: GET `https://careers.qualcomm.com/api/pcsx/search?domain=qualcomm.com&query=<מילה>&location=Israel&start=0`. Teva: GET `https://www.careers.teva/api/apply/v2/jobs?domain=tevapharm.com&location=Israel&start=0&num=10`. ⚠️ כל דומיין עונה רק לאחת משתי הכתובות (השנייה 403) |
| Comeet | DriveNets, HiBob, Nova, SolarEdge (כנראה) | מזהי משרה בפורמט Comeet בעמודי הקריירה; Nova מציגה משרות בנתיב `novami.com/comeetitem/...`. SolarEdge — משרות שלה מופיעות באתרים חיצוניים "Powered by Comeet", ואתר החברה חוסם (403); לאמת בבנייה. ה-API של Comeet דורש company uid + token מתוך עמוד הקריירה — לחלץ בשלב הבנייה |

### שכבה 2 — חברות גדולות עם אתר עצמי (מתאם לכל אחת, אחרי שכבה 1)

| חברה | אתר המשרות |
|---|---|
| Check Point | `careers.checkpoint.com` |
| Palo Alto Networks (**כולל CyberArk**) | `jobs.paloaltonetworks.com` — `careers.cyberark.com` מפנה היום ל-`paloaltonetworks.com/idira` (המיזוג) |
| Amazon (כולל Annapurna Labs) | `amazon.jobs` |
| Google, Apple, Microsoft, Oracle | אתרי הקריירה שלהן |
| monday.com | `monday.com/careers/<uuid>` (אתר עצמי) |
| Wix | `careers.wix.com/positions` (אתר Wix) |
| Deloitte | `careers.deloitte.co.il` |
| QualityAI (לשעבר Qualitest) | `careers.qualitestgroup.com` |

### שכבה 3 — בלי סוכן משלהן (המשרות מגיעות דרך סוכני אתרי החיפוש, שלב 9)

| חברה | סיבה |
|---|---|
| Elbit | HTTP 403 |
| Rafael | העמוד נבנה בדפדפן ומגיע ריק |
| IAI | אתר עצמי מסובך (`jobs.iai.co.il`) |
| DRS RADA | HTTP 403 (גם `leonardodrs.com`) |
| ONE Technologies | HTTP 403 |
| חברות השמה: Matrix (`matrix.co.il/jobs`), Ness (`ness-tech.co.il/careers`), GAV (`gav.co.il/jobs`), abra (`abra-it.com/career`), Commit (`commit.co.il`), Aman (`aman.co.il/careers`), G-STAT (`g-stat.com/careers`), Experis (`experis.co.il/search`), Bynet (`bynet.co.il/career`) | אתרי WordPress / עצמיים, כל אחד במבנה אחר; מפרסמות בשם חברות אחרות — וממילא מופיעות באתרי החיפוש. אם יתברר בשבוע הצל שמפספסים מהן משרות — נוסיף מתאם |

⚠️ מלכודות: SmartRecruiters מחזיר HTTP 200 גם לחברה שלא קיימת (רשימה ריקה) — לבדוק `totalFound`. גם Workable מחזיר 200 עם רשימה ריקה לכל שם — לא סימן לקיום.

סה"כ ~4,500 משרות פתוחות — לכן הסינון באתר + "רק משרות חדשות" הם קריטיים.
