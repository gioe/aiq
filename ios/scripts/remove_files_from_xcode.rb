#!/usr/bin/env ruby
# Script to remove files from the Xcode project and disk
# Usage: ruby remove_files_from_xcode.rb [--keep-files] <file_path1> <file_path2> ...
# Example: ruby remove_files_from_xcode.rb AIQ/ViewModels/OldViewModel.swift
# Example: ruby remove_files_from_xcode.rb --keep-files AIQ/openapi.json

require 'xcodeproj'

# Parse options
keep_files = ARGV.delete('--keep-files')

if ARGV.empty?
  puts "Usage: ruby remove_files_from_xcode.rb [--keep-files] <file_path1> <file_path2> ..."
  puts "Example: ruby remove_files_from_xcode.rb AIQ/ViewModels/OldViewModel.swift"
  puts ""
  puts "Options:"
  puts "  --keep-files  Remove from project but do not delete files from disk"
  exit 1
end

# Change to the ios directory if not already there
Dir.chdir(File.dirname(__FILE__) + '/..')

# Open the Xcode project
project_path = 'AIQ.xcodeproj'
unless File.exist?(project_path)
  puts "Error: Could not find #{project_path}"
  exit 1
end

project = Xcodeproj::Project.open(project_path)

# Process each file
ARGV.each do |file_path|
  # Determine the group path from the file path
  path_parts = file_path.split('/')
  file_name = path_parts.pop

  # Find the group containing the file
  group = project.main_group
  found = true
  path_parts.each do |part|
    existing_group = group[part]
    if existing_group.nil?
      puts "✗ Group not found in project: #{path_parts.join('/')}"
      found = false
      break
    end
    group = existing_group
  end
  next unless found

  # Find the file reference in the group
  file_ref = group.files.find { |f| f.path == file_name }
  if file_ref.nil?
    puts "⚠ File not found in project: #{file_path}"
    next
  end

  # Remove from all build phases across all targets
  project.targets.each do |target|
    target.build_phases.each do |phase|
      phase.files.select { |bf| bf.file_ref == file_ref }.each do |build_file|
        build_file.remove_from_project
      end
    end
  end

  # Remove the file reference from the project
  file_ref.remove_from_project

  # Delete from disk unless --keep-files was passed
  if keep_files
    puts "✓ Removed #{file_path} from project (file kept on disk)"
  elsif File.exist?(file_path)
    File.delete(file_path)
    puts "✓ Removed #{file_path} from project and deleted from disk"
  else
    puts "✓ Removed #{file_path} from project (file was not on disk)"
  end
end

# Save the project
project.save
puts "✓ Project saved successfully"
