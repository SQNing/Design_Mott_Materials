#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "Spglib::symspg" for configuration "Release"
set_property(TARGET Spglib::symspg APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(Spglib::symspg PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libsymspg.so.2.1.0"
  IMPORTED_SONAME_RELEASE "libsymspg.so.2"
  )

list(APPEND _IMPORT_CHECK_TARGETS Spglib::symspg )
list(APPEND _IMPORT_CHECK_FILES_FOR_Spglib::symspg "${_IMPORT_PREFIX}/lib/libsymspg.so.2.1.0" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
