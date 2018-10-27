SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET AUTOCOMMIT = 0;
START TRANSACTION;
SET time_zone = "+00:00";

--
-- Database: `botjagwar`
--

-- --------------------------------------------------------

--
-- Table structure for table `definitions`
--

CREATE TABLE `definitions` (
  `id` int(11) NOT NULL,
  `date_changed` datetime DEFAULT NULL,
  `definition` varchar(250) DEFAULT NULL,
  `definition_language` varchar(6) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Triggers `definitions`
--
DELIMITER $$
CREATE TRIGGER `on_definition_changed` AFTER UPDATE ON `definitions` FOR EACH ROW insert into events_definition_changed
(
 	definition_id,
    old_definition,
    new_definition,
 	commentary,
 	change_datetime,
    status_datetime,
 	status
) VALUES 
(
 	NEW.id,
    OLD.definition,
    NEW.definition,
    'definition-changed',
 	CURRENT_TIMESTAMP(),
	CURRENT_TIMESTAMP(),
    'PENDING'
)
$$
DELIMITER ;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `definitions`
--
ALTER TABLE `definitions`
  ADD PRIMARY KEY (`id`),
  ADD KEY `date_changed` (`date_changed`,`definition`(191),`definition_language`),
  ADD KEY `definition` (`definition`(191),`definition_language`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `definitions`
--
ALTER TABLE `definitions`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;COMMIT;
