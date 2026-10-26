-- Lab 3, Part II: Library - Books and Authors
-- Jana Bassem, 2304066 | Farida Mohamed, 2304245
-- WARNING: re-running this script replaces this assignment database.
-- Lecture 3: CREATE TABLE, INT, VARCHAR, DECIMAL, NOT NULL,
-- PRIMARY KEY, FOREIGN KEY and ON DELETE CASCADE.
DROP DATABASE IF EXISTS library_lab3_2304066;
CREATE DATABASE library_lab3_2304066;
USE library_lab3_2304066;

-- The parent table must exist before BOOK can reference it.
CREATE TABLE AUTHOR (
    author_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    country VARCHAR(50) NOT NULL,
    PRIMARY KEY (author_id)
);

CREATE TABLE BOOK (
    book_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    author_id INT NOT NULL,
    PRIMARY KEY (book_id),
    FOREIGN KEY (author_id) REFERENCES AUTHOR(author_id)
        ON DELETE CASCADE
);
