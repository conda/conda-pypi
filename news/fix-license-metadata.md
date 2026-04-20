### Bug fixes

* Fix license metadata extraction from wheel METADATA files. The code was using underscore keys (`license_expression`, `license`) but `email.message.Message` requires hyphen keys matching the actual METADATA headers (`License-Expression`, `License`).
