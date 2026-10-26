-- Insert authors first, then their books. Run after problem2_DDL.sql.
-- Jana Bassem, 2304066 | Farida Mohamed, 2304245
-- Re-running this DML alone produces duplicate primary-key errors.
USE library_lab3_2304066;

INSERT INTO AUTHOR (author_id, name, country)
VALUES (1, 'Naguib Mahfouz', 'Egypt');
INSERT INTO AUTHOR (author_id, name, country)
VALUES (2, 'Jane Austen', 'United Kingdom');
INSERT INTO AUTHOR (author_id, name, country)
VALUES (3, 'Jules Verne', 'France');

INSERT INTO BOOK (book_id, title, price, author_id)
VALUES (101, 'Palace Walk', 18.50, 1);
INSERT INTO BOOK (book_id, title, price, author_id)
VALUES (102, 'Midaq Alley', 14.75, 1);
INSERT INTO BOOK (book_id, title, price, author_id)
VALUES (103, 'Pride and Prejudice', 12.00, 2);
INSERT INTO BOOK (book_id, title, price, author_id)
VALUES (104, 'Emma', 11.50, 2);
INSERT INTO BOOK (book_id, title, price, author_id)
VALUES (105, 'Around the World in Eighty Days', 16.25, 3);
INSERT INTO BOOK (book_id, title, price, author_id)
VALUES (106, 'Journey to the Centre of the Earth', 15.00, 3);
