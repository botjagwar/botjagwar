
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET AUTOCOMMIT = 0;
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `botjagwar`
--

-- --------------------------------------------------------

--
-- Table structure for table `events_definition_changed`
--

CREATE TABLE `events_definition_changed` (
  `id` int(11) NOT NULL,
  `definition_id` int(11) NOT NULL,
  `change_datetime` datetime NOT NULL,
  `status` enum('PENDING','PROCESSING','DONE','FAILED') NOT NULL DEFAULT 'PENDING',
  `status_datetime` datetime NOT NULL,
  `old_definition` varchar(255) NOT NULL,
  `new_definition` varchar(255) NOT NULL,
  `commentary` text
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `events_definition_changed`
--
ALTER TABLE `events_definition_changed`
  ADD PRIMARY KEY (`id`),
  ADD KEY `definition_id` (`definition_id`,`old_definition`(191),`new_definition`(191)),
  ADD KEY `status` (`status`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `events_definition_changed`
--
ALTER TABLE `events_definition_changed`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=25;COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
