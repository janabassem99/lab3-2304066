# Part II discussion notes

**Jana Bassem - 2304066**  
**Farida Mohamed - 2304245**

## 1. What does the project do?

It manages authors and their books. It shows both tables and lets the user add, edit and remove rows. Book covers and author photos are optional upload bonuses. The website writes to the same MySQL database that DBeaver displays.

The flow is: browser form > Flask route > parameterized SQL > MySQL > updated page. HTML structures the page, CSS styles it, and JavaScript provides the image preview and theme switch. Python handles requests, validation and images. SQL stores and retrieves the records.

## 2. Which table is the parent?

AUTHOR is the parent. BOOK is the child.

```text
AUTHOR 1 -------- many BOOK
author_id (PK)         author_id (FK)
                      book_id   (PK)
```

An author can have zero, one or many books. Every book in this implementation has exactly one existing author because `BOOK.author_id` is `NOT NULL` and a foreign key.

## 3. Why these data types and constraints?

| Choice | Explanation |
| --- | --- |
| INT | Whole-number IDs |
| VARCHAR(100) | Author names, up to 100 characters |
| VARCHAR(50) | Countries, up to 50 characters |
| VARCHAR(150) | Book titles, up to 150 characters |
| DECIMAL(10,2) | Exact fixed-point prices: 10 digits in total, 2 after the decimal point |
| PRIMARY KEY | Uniquely identifies a row; cannot be duplicated or NULL |
| FOREIGN KEY | Prevents a book from referring to an author who does not exist |
| NOT NULL | Rejects missing SQL values |
| ON DELETE CASCADE | Automatically deletes an author's books when that author is deleted |

`NOT NULL` does not reject an empty string or spaces. Python strips and checks text. Python also rejects negative/nonfinite prices, more than two meaningful decimal places and invalid IDs. The SQL schema stays within the taught constraints, so these extra input rules live in the application, not an advanced SQL feature.

IDs are entered manually so the SQL needs no additional ID-generation feature. On edit, primary key fields stay fixed. You can change a book's author to another existing author.

## 4. Why create and insert AUTHOR first?

BOOK references AUTHOR, so the referenced table must exist before its foreign key can be created. An author row must exist before a book can use that author_id. Running DML before DDL fails because the database/tables do not exist. Running seed DML twice fails because primary keys must be unique.

## 5. What is referential integrity?

The lecture permits a foreign key to be NULL or to match an existing referenced key. This assignment implementation adds `NOT NULL`, so every book's author_id must match an existing author.

```sql
INSERT INTO BOOK (book_id, title, price, author_id)
VALUES (9003, 'Invalid Author Example', 10.00, 999999);
```

If author 999999 does not exist, MySQL rejects the statement with error **1452**, reporting that a child row cannot be added or updated because the foreign key fails. The website shows a clearer message and does not insert the row. The same rule also applies when updating a book's author_id.

## 6. What happens when an author is deleted?

The app runs:

```sql
DELETE FROM AUTHOR WHERE author_id = 9001;
```

MySQL sees the foreign key's `ON DELETE CASCADE` rule and automatically removes every BOOK row whose author_id is 9001. The app does not send a separate DELETE for those book rows. Books by other authors remain.

Deleting one book has no reverse cascade: its author remains. Cascade follows the parent-to-child direction defined by the FK.

The app separately removes uploaded image files because SQL cascade only affects database rows.

## 7. What are the queries for each feature?

The website uses `%s` placeholders. Values are passed separately to PyMySQL. These placeholders are Python connector syntax; when demonstrating by hand in DBeaver, use concrete values as shown in `problem2_discussion.sql`.

```sql
-- F2.1
SELECT book_id, title, price, author_id FROM BOOK;
SELECT author_id, name, country FROM AUTHOR;

-- F2.2
INSERT INTO AUTHOR (author_id, name, country) VALUES (%s, %s, %s);
INSERT INTO BOOK (book_id, title, price, author_id) VALUES (%s, %s, %s, %s);

-- F2.3
UPDATE AUTHOR SET name = %s, country = %s WHERE author_id = %s;
UPDATE BOOK SET title = %s, price = %s, author_id = %s WHERE book_id = %s;

-- F2.4
DELETE FROM BOOK WHERE book_id = %s;

-- F2.5
DELETE FROM AUTHOR WHERE author_id = %s;
```

Without a WHERE clause, UPDATE or DELETE would affect every row. A book's author is selected from existing authors, but the database foreign key still enforces integrity if a request is altered.

The app reads related books with a simple `SELECT ... FROM BOOK WHERE author_id = %s` to preview a cascade deletion. It does not need a JOIN. It reads both tables separately and calculates counts in Python.

## 8. Where is the image bonus?

Both Add/Edit forms use a file input and `enctype="multipart/form-data"`. Flask receives the image in `request.files`. Pillow validates the image bytes, resizes overly large dimensions within the accepted limit, and saves a normalized PNG in the local uploads folder.

An author's photo is `author-<author_id>.png`. A book's cover is `book-<book_id>.png`. This keeps the exact lab schema. The form previews the selected file before submission. Saving persists it, replacing updates it, and the Remove current image checkbox deletes it without removing the database record.

The initials shown before any upload are visual placeholders. They are not evidence of the bonus. To demonstrate the bonus, upload a real image for an author and for a book, save, and reload.

## 9. What do commit, placeholders and form tokens mean?

- `connection.commit()` makes the INSERT, UPDATE or DELETE persistent.
- `cursor.execute(sql, values)` keeps form input separate from the SQL structure.
- The form token checks that a POST came from a form generated by the app. It is application protection, not a SQL construct.
- Jinja escapes displayed user text so a title containing HTML is shown as text.
- GET opens or previews a page. POST performs a change. Opening a Remove page alone does not delete a record.

These are implementation details of the website. They do not introduce advanced SQL into the assignment.

## 10. How does this connect to the lectures?

| Material | Connection to this project |
| --- | --- |
| Lecture 1, slides 2-4 | Database vs DBMS; defining, constructing and manipulating data |
| Lecture 1, slides 62-64 | Schema is the structure; instance/state is the current data |
| Lecture 2, slides 5, 10, 13-14 | Relation, tuple, attribute, domain, degree and relation state |
| Lecture 2, slides 21, 25-26 | Keys, uniqueness, candidate/primary keys and NOT NULL |
| Lecture 2, slides 30-32 | Entity integrity and referential integrity |
| Lecture 2, slides 34-39 | INSERT, DELETE and UPDATE can affect constraints |
| Lecture 3, slides 14-19 | DDL, data types, CREATE TABLE and key declarations |
| Lecture 3, slides 22-25 | Referential actions including ON DELETE CASCADE |
| LAB3.pdf, page 1 | MySQL setup, basic SELECT/INSERT/UPDATE/DELETE and WHERE examples |
| LAB3.pdf, pages 2-3 | Exact AUTHOR/BOOK schema, F2.1-F2.5 and both upload bonuses |
| Lecture 4, slides 8-15 | Selection chooses rows, projection chooses attributes; the simple SELECT queries reflect those concepts |

SQL SELECT can combine row filtering and attribute selection. It is not identical to the relational algebra selection operator alone. Classical algebra projection removes duplicates, while ordinary SQL SELECT can retain duplicates; the app's displayed rows have distinct primary keys.

## Short spoken explanation in Egyptian Arabic

المشروع عبارة عن مكتبة بسيطة فيها جدولين: AUTHOR وBOOK. الـAUTHOR هو الجدول الأساسي، والـBOOK فيه author_id كـForeign Key بيرجع لمؤلف موجود. كل كتاب لازم يكون ليه مؤلف، لكن المؤلف ممكن يكون ليه أكتر من كتاب أو ميبقاش عنده كتب لسه.

استخدمنا INT للأرقام، وVARCHAR للنصوص، وDECIMAL(10,2) للسعر. الـPrimary Key بيمنع التكرار وNULL، والـForeign Key بيحافظ على Referential Integrity. لو حاولنا نضيف كتاب لمؤلف مش موجود، MySQL بيرفض العملية.

لما بنمسح مؤلف، ON DELETE CASCADE بيمسح كتبه تلقائيًا من قاعدة البيانات. لو مسحنا كتاب بس، المؤلف بيفضل موجود. الصور بتتخزن كملفات في فولدر uploads، عشان نحافظ على نفس الجدولين والأعمدة المطلوبة. فيه رفع صورة للكتاب وصورة للمؤلف، وده البونص.

الـSQL المستخدم بسيط: SELECT وINSERT وUPDATE وDELETE، ومع التعديل أو المسح بنستخدم WHERE عشان نحدد السطر المطلوب. مفيش JOIN ولا GROUP BY ولا HAVING. الترتيب وعدّ الكتب معمولين في Python.
