-- Optional: open in DBeaver for the discussion.
-- Jana Bassem 2304066 | Farida Mohamed 2304245
USE library_lab3_2304066;

-- F2.1: two separate SELECT statements. No JOIN.
SELECT book_id, title, price, author_id FROM BOOK;
SELECT author_id, name, country FROM AUTHOR;

-- The following examples use temporary demonstration IDs.
-- Run the statements individually to see each change.

-- F2.2: add an author before adding a book that refers to them.
INSERT INTO AUTHOR (author_id, name, country)
VALUES (9001, 'Discussion Author', 'Egypt');
INSERT INTO BOOK (book_id, title, price, author_id)
VALUES (9001, 'Discussion Book', 20.00, 9001);

-- F2.3: edit non-key values. The website keeps IDs unchanged on edit.
UPDATE AUTHOR SET name = 'Updated Author', country = 'Egypt'
WHERE author_id = 9001;
UPDATE BOOK SET title = 'Updated Book', price = 22.50, author_id = 9001
WHERE book_id = 9001;

-- F2.4: removing a child does not remove its parent.
DELETE FROM BOOK WHERE book_id = 9001;
SELECT author_id, name, country FROM AUTHOR WHERE author_id = 9001;

-- F2.5: insert another child, then demonstrate ON DELETE CASCADE.
INSERT INTO BOOK (book_id, title, price, author_id)
VALUES (9002, 'Cascade Example', 10.00, 9001);
DELETE FROM AUTHOR WHERE author_id = 9001;
SELECT book_id, title, price, author_id FROM BOOK WHERE author_id = 9001;
-- Result: no rows. MySQL deleted the associated book automatically.

-- Referential integrity demonstration: run alone; EXPECT error 1452.
-- Do not include this failing statement in your setup scripts.
-- INSERT INTO BOOK (book_id, title, price, author_id)
-- VALUES (9003, 'Invalid Author Example', 10.00, 999999);
