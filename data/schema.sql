
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

-- Database: `data_botjagwar`
CREATE DATABASE IF NOT EXISTS `data_botjagwar` DEFAULT CHARACTER SET latin1 COLLATE latin1_swedish_ci;
USE `data_botjagwar`;

-- Table structure for table `anglisy`
DROP TABLE IF EXISTS `anglisy`;
CREATE TABLE IF NOT EXISTS `anglisy` (
  `en_wID` int(11) NOT NULL,
  `pos_ID` int(11) NOT NULL,
  `anglisy` varchar(30) NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

-- Table structure for table `anglisy_malagasy`
DROP TABLE IF EXISTS `anglisy_malagasy`;
CREATE TABLE IF NOT EXISTS `anglisy_malagasy` (
  `en_wID` int(11) NOT NULL,
  `mg` varchar(30) NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

DROP VIEW IF EXISTS `en_mg`;

DROP TABLE IF EXISTS `frantsay`;
CREATE TABLE IF NOT EXISTS `frantsay` (
  `fr_wID` int(11) NOT NULL,
  `pos_ID` int(11) NOT NULL,
  `frantsay` varchar(25) CHARACTER SET latin1 NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

-- Table structure for table `frantsay_malagasy`
DROP TABLE IF EXISTS `frantsay_malagasy`;
CREATE TABLE IF NOT EXISTS `frantsay_malagasy` (
  `fr_wID` int(11) NOT NULL,
  `mg` varchar(40) NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

DROP VIEW IF EXISTS `fr_mg`;

DROP TABLE IF EXISTS `teny`;
CREATE TABLE IF NOT EXISTS `teny` (
  `laharana` int(11) NOT NULL,
  `teny` varchar(255) COLLATE utf8_unicode_ci NOT NULL,
  `karazany` varchar(10) COLLATE utf8_unicode_ci NOT NULL,
  `famaritana` text COLLATE utf8_unicode_ci NOT NULL,
  `famaritana_fiteny` varchar(5) COLLATE utf8_unicode_ci NOT NULL DEFAULT 'mg',
  `fiteny` varchar(8) COLLATE utf8_unicode_ci NOT NULL,
  `fanononana` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '--',
  `daty` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=MyISAM DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

DROP TABLE IF EXISTS `en_mg`;
DROP TABLE IF EXISTS `fr_mg`;

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost`
    SQL SECURITY DEFINER VIEW `en_mg` AS
    select
        `anglisy`.`anglisy` AS `en`,
        `anglisy_malagasy`.`mg` AS `mg`
    from
        `anglisy_malagasy`, `anglisy`
    where
        `anglisy_malagasy`.en_wID = `anglisy`.`en_wID`;
        
-- Structure for view `fr_mg`

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost`
    SQL SECURITY DEFINER VIEW `fr_mg` AS
    select
        `frantsay`.`frantsay` AS `fr`,
        `frantsay_malagasy`.`mg` AS `mg`
    from
        `frantsay_malagasy`, `frantsay`
    where
        `frantsay_malagasy`.fr_wID = `frantsay`.`fr_wID`;
        

-- Indexes for dumped tables

-- Indexes for table `anglisy`
ALTER TABLE `anglisy`
  ADD PRIMARY KEY (`en_wID`),
  ADD FULLTEXT( `anglisy`);

-- Indexes for table `anglisy_malagasy`
ALTER TABLE `anglisy_malagasy`
  ADD UNIQUE KEY `en_wID_3` (`en_wID`,`mg`),
  ADD KEY `en_wID` (`en_wID`);

-- Indexes for table `frantsay`
ALTER TABLE `frantsay`
  ADD PRIMARY KEY (`fr_wID`),
  ADD FULLTEXT( `frantsay`);

-- Indexes for table `frantsay_malagasy`
ALTER TABLE `frantsay_malagasy`
  ADD KEY `fr_wID` (`fr_wID`),
  ADD UNIQUE KEY `fr_wID_2` (`fr_wID`,`mg`);

-- Indexes for table `teny`
ALTER TABLE `teny`
  ADD PRIMARY KEY (`laharana`),
  ADD KEY `teny` (`teny`,`fiteny`);

ALTER TABLE `anglisy`
  MODIFY `en_wID` int(11) NOT NULL AUTO_INCREMENT;
ALTER TABLE `frantsay`
  MODIFY `fr_wID` int(11) NOT NULL AUTO_INCREMENT;
ALTER TABLE `frantsay_malagasy`
  MODIFY `fr_wID` int(11) NOT NULL AUTO_INCREMENT;
ALTER TABLE `teny`
  MODIFY `laharana` int(11) NOT NULL AUTO_INCREMENT;