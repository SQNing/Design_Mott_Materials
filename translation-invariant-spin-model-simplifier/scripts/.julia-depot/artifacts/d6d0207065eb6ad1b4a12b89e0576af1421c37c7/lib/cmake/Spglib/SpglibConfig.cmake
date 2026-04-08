
####### Expanded from @PACKAGE_INIT@ by configure_package_config_file() #######
####### Any changes to this file will be overwritten by the next CMake run ####
####### The input file was SpglibConfig.cmake.in                            ########

get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../../../" ABSOLUTE)

macro(set_and_check _var _file)
  set(${_var} "${_file}")
  if(NOT EXISTS "${_file}")
    message(FATAL_ERROR "File or directory ${_file} referenced by variable ${_var} does not exist !")
  endif()
endmacro()

macro(check_required_components _NAME)
  foreach(comp ${${_NAME}_FIND_COMPONENTS})
    if(NOT ${_NAME}_${comp}_FOUND)
      if(${_NAME}_FIND_REQUIRED_${comp})
        set(${_NAME}_FOUND FALSE)
      endif()
    endif()
  endforeach()
endmacro()

####################################################################################


## Define basic variables
# Defined components in the project
set(Spglib_Supported_Comps static shared omp fortran)
# Define deprecated components. For each deprecated component define ${comp}_Replacement
set(Spglib_Deprecated_Comps "")
set(Spglib_Fortran OFF)
set(Spglib_Python OFF)
set(Spglib_OMP OFF)
set(Spglib_LIB_TYPE )

## Parse find_package request

if (NOT EXISTS ${CMAKE_CURRENT_LIST_DIR}/PackageCompsHelper.cmake)
	message(WARNING "Missing helper file PackageCompsHelper.cmake")
	set(Spglib_FOUND FALSE)
	return()
endif()

include(${CMAKE_CURRENT_LIST_DIR}/PackageCompsHelper.cmake)
find_package_with_comps(PACKAGE Spglib PRINT LOAD_ALL_DEFAULT HAVE_GLOBAL_SHARED_STATIC)

check_required_components(Spglib)
