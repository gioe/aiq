#!/usr/bin/env ruby
# Script to add files to the Xcode project
# Usage: ruby add_files_to_xcode.rb [--no-target] [--ascii] <file_path1> <file_path2> ...
# Example: ruby add_files_to_xcode.rb AIQ/ViewModels/MyViewModel.swift
# Example: ruby add_files_to_xcode.rb --no-target AIQ/openapi.json AIQ/openapi-generator-config.yaml

require 'xcodeproj'

# Parse options
no_target = ARGV.delete('--no-target')
ascii_mode = ARGV.delete('--ascii') || ENV['CI'] || ENV['TERM'] == 'dumb'

OK   = ascii_mode ? '[OK]'    : '✓'
ERR  = ascii_mode ? '[ERROR]' : '✗'
WARN = ascii_mode ? '[WARN]'  : '⚠'

if ARGV.empty?
  puts "Usage: ruby add_files_to_xcode.rb [--no-target] [--ascii] <file_path1> <file_path2> ..."
  puts "Example: ruby add_files_to_xcode.rb AIQ/ViewModels/MyViewModel.swift"
  puts "Example: ruby add_files_to_xcode.rb --no-target AIQ/openapi.json"
  puts ""
  puts "Options:"
  puts "  --no-target  Add file to project without adding to any build target"
  puts "  --ascii      Use ASCII status symbols ([OK]/[ERROR]/[WARN]) instead of Unicode (auto-detected in CI)"
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
sharedkit_test_target = project.targets.find { |t| t.name == 'SharedKitTests' }

# Process each file
ARGV.each do |file_path|
  unless File.exist?(file_path)
    puts "#{ERR} File not found: #{file_path}"
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
      puts "#{ERR} Group not found in project: #{path_parts.join('/')}"
      break
    end
    group = existing_group
  end

  # Compute the relative path from the nearest ancestor group that has a real
  # path on disk.  Groups like Features/Test/Views often have empty `path`
  # attributes (virtual groups), so file references under them must carry the
  # full relative path back to the first ancestor whose `path` is set.
  relative_prefix_parts = []
  g = group
  while g && g != project.main_group
    relative_prefix_parts.unshift(g.name) if g.path.nil? || g.path.empty?
    break unless g.path.nil? || g.path.empty?
    g = g.parent
  end
  relative_path = if relative_prefix_parts.empty?
    file_name
  else
    File.join(*relative_prefix_parts, file_name)
  end

  # Check if file already exists in the group (match by filename or full path)
  existing_file = group.files.find { |f| f.path == file_name || f.path == relative_path || f.name == file_name }
  if existing_file
    puts "#{WARN} File already in project: #{file_path}"
    # Remove it first if path is wrong
    if existing_file.real_path.to_s != File.absolute_path(file_path)
      puts "  Removing incorrect reference..."
      existing_file.remove_from_project
    else
      next
    end
  end

  # Determine the file type based on extension
  file_type = case File.extname(file_name).downcase
  when '.swift' then 'sourcecode.swift'
  when '.json' then 'text.json'
  when '.yaml', '.yml' then 'text.yaml'
  when '.plist' then 'text.plist.xml'
  when '.md' then 'net.daringfireball.markdown'
  when '.h' then 'sourcecode.c.h'
  when '.m' then 'sourcecode.c.objc'
  when '.strings' then 'text.plist.strings'
  when '.storyboard' then 'file.storyboard'
  when '.xib' then 'file.xib'
  when '.xcassets' then 'folder.assetcatalog'
  else nil
  end

  # Add the file to the group with proper file type.
  # Use the full relative path so Xcode resolves the file correctly from the
  # nearest ancestor group that has a real `path` attribute.  Set `name` to
  # just the filename for display, matching the pattern of sibling files.
  file_ref = group.new_reference(relative_path)
  file_ref.name = file_name if relative_path != file_name
  file_ref.last_known_file_type = file_type if file_type

  if no_target
    # Don't add to any target - just add to project for reference
    puts "#{OK} Added #{file_path} to project (no target)"
  else
    # Determine which target to add to based on file path
    target, target_name = if file_path.start_with?('AIQUITests/')
      [ui_test_target, 'AIQUITests']
    elsif file_path.start_with?('AIQTests/')
      [test_target, 'AIQTests']
    elsif file_path.start_with?('Packages/SharedKit/Tests/SharedKitTests/')
      [sharedkit_test_target, 'SharedKitTests']
    else
      [main_target, 'AIQ']
    end

    target.add_file_references([file_ref])
    puts "#{OK} Added #{file_path} to #{target_name} target"
  end
end

# Save the project
project.save
puts "#{OK} Project saved successfully"
