#!/usr/bin/env ruby
# Script to add Swift files to the Xcode project
# Usage: ruby add_files_to_xcode.rb <file_path1> <file_path2> ...
# Example: ruby add_files_to_xcode.rb AIQ/ViewModels/MyViewModel.swift AIQ/Views/MyView.swift

require 'xcodeproj'

if ARGV.empty?
  puts "Usage: ruby add_files_to_xcode.rb <file_path1> <file_path2> ..."
  puts "Example: ruby add_files_to_xcode.rb AIQ/ViewModels/MyViewModel.swift"
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

# Get the targets
main_target = project.targets.find { |t| t.name == 'AIQ' }
test_target = project.targets.find { |t| t.name == 'AIQTests' }
ui_test_target = project.targets.find { |t| t.name == 'AIQUITests' }

# Process each file
ARGV.each do |file_path|
  unless File.exist?(file_path)
    puts "✗ File not found: #{file_path}"
    next
  end

  # Determine the group path from the file path
  # e.g., "AIQ/ViewModels/MyViewModel.swift" -> ["AIQ", "ViewModels"]
  path_parts = file_path.split('/')
  file_name = path_parts.pop

  # Find the appropriate group
  group = project.main_group
  path_parts.each do |part|
    existing_group = group[part]
    if existing_group.nil?
      puts "✗ Group not found in project: #{path_parts.join('/')}"
      break
    end
    group = existing_group
  end

  # Check if file already exists in the group
  existing_file = group.files.find { |f| f.path == file_name }
  if existing_file
    puts "⚠ File already in project: #{file_path}"
    # Remove it first if path is wrong
    if existing_file.real_path.to_s != File.absolute_path(file_path)
      puts "  Removing incorrect reference..."
      existing_file.remove_from_project
    else
      next
    end
  end

  # Add the file to the group (use just the filename, not the full path)
  file_ref = group.new_reference(file_name)

  # Determine which target to add to based on file path
  target, target_name = if file_path.start_with?('AIQUITests/')
    [ui_test_target, 'AIQUITests']
  elsif file_path.start_with?('AIQTests/')
    [test_target, 'AIQTests']
  else
    [main_target, 'AIQ']
  end

  target.add_file_references([file_ref])
  puts "✓ Added #{file_path} to #{target_name} target"
end

# Save the project
project.save
puts "✓ Project saved successfully"
