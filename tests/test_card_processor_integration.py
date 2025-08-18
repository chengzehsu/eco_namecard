"""
Integration tests for CardProcessor
Tests complete workflow scenarios end-to-end
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import io

# Mock genai before importing to prevent initialization errors
with patch('src.namecard.infrastructure.ai.card_processor.genai') as mock_genai:
    mock_genai.configure.return_value = None
    mock_model = Mock()
    mock_model.generate_content.return_value = Mock(text='{"cards": []}')
    mock_genai.GenerativeModel.return_value = mock_model
    
    from src.namecard.infrastructure.ai.card_processor import CardProcessor, ProcessingConfig
    from src.namecard.core.models.card import BusinessCard


class TestCardProcessorIntegration:
    """Integration tests for complete CardProcessor workflows"""
    
    def setup_method(self):
        """Setup for each test"""
        with patch('src.namecard.infrastructure.ai.card_processor.genai'):
            self.processor = CardProcessor()
            self.test_user_id = "integration_test_user"
    
    def create_test_image_bytes(self, width=800, height=600, format='PNG'):
        """Create test image as bytes"""
        image = Image.new('RGB', (width, height), color='white')
        
        # Add some simple content to make it look like a business card
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        
        # Simulate business card text
        try:
            draw.text((50, 50), "John Doe", fill='black')
            draw.text((50, 100), "Software Engineer", fill='black')
            draw.text((50, 150), "Tech Company Inc.", fill='black')
            draw.text((50, 200), "john.doe@techcompany.com", fill='black')
            draw.text((50, 250), "+1-555-123-4567", fill='black')
        except:
            # If font issues, just create plain image
            pass
        
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format=format)
        return img_byte_arr.getvalue()
    
    @patch.object(CardProcessor, '_analyze_with_gemini')
    def test_single_card_complete_workflow(self, mock_analyze):
        """Test complete workflow for single business card"""
        # Mock Gemini response with complete card data
        gemini_response = {
            "cards": [{
                "name": "John Doe",
                "company": "Tech Company Inc.",
                "title": "Software Engineer",
                "phone": "+1-555-123-4567",
                "email": "john.doe@techcompany.com",
                "address": "123 Tech Street, Silicon Valley, CA 94000",
                "website": "https://techcompany.com",
                "fax": "+1-555-123-4568",
                "line_id": "johndoe_tech",
                "confidence_score": 0.95,
                "quality_score": 0.9
            }],
            "total_cards_detected": 1,
            "overall_quality": 0.9,
            "processing_notes": "High quality business card with all information clearly visible"
        }
        mock_analyze.return_value = json.dumps(gemini_response)
        
        # Create test image
        image_data = self.create_test_image_bytes()
        
        # Process the image
        cards = self.processor.process_image(image_data, self.test_user_id)
        
        # Verify results
        assert len(cards) == 1
        card = cards[0]
        
        assert card.name == "John Doe"
        assert card.company == "Tech Company Inc."
        assert card.title == "Software Engineer"
        assert card.phone == "+1-555-123-4567"
        assert card.email == "john.doe@techcompany.com"
        assert card.address == "123 Tech Street, Silicon Valley, CA 94000"
        assert card.website == "https://techcompany.com"
        assert card.fax == "+1-555-123-4568"
        assert card.line_id == "johndoe_tech"
        assert card.confidence_score == 0.95
        assert card.quality_score == 0.9
        assert card.line_user_id == self.test_user_id
        
        # Verify Gemini was called with processed image
        mock_analyze.assert_called_once()
    
    @patch.object(CardProcessor, '_analyze_with_gemini')
    def test_multiple_cards_workflow(self, mock_analyze):
        """Test workflow with multiple business cards in one image"""
        gemini_response = {
            "cards": [
                {
                    "name": "Alice Smith",
                    "company": "Design Studio",
                    "title": "Creative Director",
                    "phone": "+1-555-111-2222",
                    "email": "alice@designstudio.com",
                    "confidence_score": 0.92,
                    "quality_score": 0.88
                },
                {
                    "name": "Bob Johnson",
                    "company": "Marketing Agency",
                    "title": "Account Manager",
                    "phone": "+1-555-333-4444",
                    "email": "bob@marketingagency.com",
                    "confidence_score": 0.89,
                    "quality_score": 0.85
                }
            ],
            "total_cards_detected": 2,
            "overall_quality": 0.87,
            "processing_notes": "Two business cards detected with good quality"
        }
        mock_analyze.return_value = json.dumps(gemini_response)
        
        # Create larger test image to simulate multiple cards
        image_data = self.create_test_image_bytes(width=1600, height=800)
        
        cards = self.processor.process_image(image_data, self.test_user_id)
        
        assert len(cards) == 2
        
        # Verify first card
        assert cards[0].name == "Alice Smith"
        assert cards[0].company == "Design Studio"
        assert cards[0].line_user_id == self.test_user_id
        
        # Verify second card
        assert cards[1].name == "Bob Johnson"
        assert cards[1].company == "Marketing Agency"
        assert cards[1].line_user_id == self.test_user_id
    
    @patch.object(CardProcessor, '_analyze_with_gemini')
    def test_low_quality_cards_filtered_out(self, mock_analyze):
        """Test that low quality cards are filtered out"""
        gemini_response = {
            "cards": [
                {
                    "name": "Good Quality Card",
                    "company": "Quality Corp",
                    "phone": "+1-555-999-8888",
                    "confidence_score": 0.95,
                    "quality_score": 0.9
                },
                {
                    "name": "Low Confidence Card",
                    "company": "Unclear Corp",
                    "phone": "+1-555-777-6666",
                    "confidence_score": 0.2,  # Below threshold
                    "quality_score": 0.9
                },
                {
                    "name": "Low Quality Card",
                    "company": "Blurry Corp",
                    "phone": "+1-555-555-4444",
                    "confidence_score": 0.9,
                    "quality_score": 0.1  # Below threshold
                }
            ],
            "total_cards_detected": 3,
            "overall_quality": 0.6
        }
        mock_analyze.return_value = json.dumps(gemini_response)
        
        image_data = self.create_test_image_bytes()
        cards = self.processor.process_image(image_data, self.test_user_id)
        
        # Only high quality card should pass validation
        assert len(cards) == 1
        assert cards[0].name == "Good Quality Card"
    
    @patch.object(CardProcessor, '_analyze_with_gemini')
    def test_incomplete_cards_filtered_out(self, mock_analyze):
        """Test that cards missing essential information are filtered"""
        gemini_response = {
            "cards": [
                {
                    "name": "Complete Card",
                    "company": "Complete Corp",
                    "phone": "+1-555-123-4567",
                    "confidence_score": 0.9,
                    "quality_score": 0.8
                },
                {
                    "confidence_score": 0.9,  # Missing name and company
                    "quality_score": 0.8
                },
                {
                    "name": "Contact Missing",
                    "company": "No Contact Corp",
                    "confidence_score": 0.9,
                    "quality_score": 0.8
                    # Missing all contact information
                }
            ]
        }
        mock_analyze.return_value = json.dumps(gemini_response)
        
        image_data = self.create_test_image_bytes()
        cards = self.processor.process_image(image_data, self.test_user_id)
        
        # Only complete card should pass validation
        assert len(cards) == 1
        assert cards[0].name == "Complete Card"
    
    @patch.object(CardProcessor, '_analyze_with_gemini')
    def test_malformed_gemini_response_handling(self, mock_analyze):
        """Test handling of malformed Gemini responses"""
        malformed_responses = [
            "Not JSON at all",
            '{"invalid": json syntax}',
            '{"cards": "not an array"}',
            '{"cards": [{"invalid_card": true}]}',
            "",
            None
        ]
        
        image_data = self.create_test_image_bytes()
        
        for response in malformed_responses:
            mock_analyze.return_value = response
            cards = self.processor.process_image(image_data, self.test_user_id)
            assert len(cards) == 0, f"Should return empty list for response: {response}"
    
    @patch.object(CardProcessor, '_analyze_with_gemini')
    def test_image_preprocessing_integration(self, mock_analyze):
        """Test that image preprocessing works correctly in full workflow"""
        mock_analyze.return_value = json.dumps({
            "cards": [{
                "name": "Test User",
                "company": "Test Corp",
                "phone": "123-456-7890",
                "confidence_score": 0.9,
                "quality_score": 0.8
            }]
        })
        
        # Test with oversized image
        large_image_data = self.create_test_image_bytes(width=4000, height=3000)
        
        cards = self.processor.process_image(large_image_data, self.test_user_id)
        
        # Should successfully process despite large size
        assert len(cards) == 1
        assert cards[0].name == "Test User"
        
        # Verify Gemini was called (meaning preprocessing succeeded)
        mock_analyze.assert_called_once()
        
        # The actual image passed to Gemini should be resized
        called_args = mock_analyze.call_args[0]
        processed_image = called_args[0]  # First argument should be the processed image
        assert processed_image.size[0] <= 1920
        assert processed_image.size[1] <= 1920
    
    @patch.object(CardProcessor, '_analyze_with_gemini')
    def test_different_image_formats_workflow(self, mock_analyze):
        """Test workflow with different image formats"""
        mock_analyze.return_value = json.dumps({
            "cards": [{
                "name": "Format Test User",
                "company": "Format Corp",
                "phone": "123-456-7890",
                "confidence_score": 0.9,
                "quality_score": 0.8
            }]
        })
        
        formats = ['PNG', 'JPEG']
        
        for fmt in formats:
            image_data = self.create_test_image_bytes(format=fmt)
            cards = self.processor.process_image(image_data, self.test_user_id)
            
            assert len(cards) == 1
            assert cards[0].name == "Format Test User"
    
    def test_processing_suggestions_integration(self):
        """Test processing suggestions with realistic scenarios"""
        # Test with mixed quality results
        cards = [
            BusinessCard(
                name="High Quality Card",
                company="Perfect Corp",
                phone="123-456-7890",
                email="perfect@corp.com",
                confidence_score=0.95,
                quality_score=0.9,
                line_user_id=self.test_user_id
            ),
            BusinessCard(
                name="Low Confidence Card",
                company="Unclear Corp",
                phone="987-654-3210",
                confidence_score=0.6,  # Low confidence
                quality_score=0.8,
                line_user_id=self.test_user_id
            ),
            BusinessCard(
                name="Incomplete Card",
                confidence_score=0.9,
                quality_score=0.8,
                line_user_id=self.test_user_id
                # Missing company and contact info
            )
        ]
        
        suggestions = self.processor.get_processing_suggestions(cards)
        
        # Should have multiple relevant suggestions
        assert len(suggestions) >= 3
        assert any("檢測到 3 張名片" in s for s in suggestions)
        assert any("信心度較低" in s for s in suggestions)
        assert any("資訊不完整" in s for s in suggestions)
    
    @patch.object(CardProcessor, '_analyze_with_gemini')
    def test_error_recovery_workflow(self, mock_analyze):
        """Test error recovery in complete workflow"""
        # First call fails, should return empty list gracefully
        mock_analyze.side_effect = Exception("Gemini API temporarily unavailable")
        
        image_data = self.create_test_image_bytes()
        
        # Should not raise exception, should return empty list
        cards = self.processor.process_image(image_data, self.test_user_id)
        assert len(cards) == 0
    
    @patch.object(CardProcessor, '_analyze_with_gemini')
    def test_custom_config_integration(self, mock_analyze):
        """Test workflow with custom configuration"""
        # Create processor with stricter thresholds
        strict_config = ProcessingConfig(
            min_confidence_threshold=0.8,
            min_quality_threshold=0.7,
            max_image_size=(1024, 1024)
        )
        
        with patch('src.namecard.infrastructure.ai.card_processor.genai'):
            strict_processor = CardProcessor(config=strict_config)
        
        # Mock response with card that would pass default thresholds but not strict ones
        mock_analyze.return_value = json.dumps({
            "cards": [{
                "name": "Borderline Quality",
                "company": "Borderline Corp",
                "phone": "123-456-7890",
                "confidence_score": 0.75,  # Below strict threshold
                "quality_score": 0.65      # Below strict threshold
            }]
        })
        
        image_data = self.create_test_image_bytes()
        cards = strict_processor.process_image(image_data, self.test_user_id)
        
        # Should be filtered out due to strict thresholds
        assert len(cards) == 0
    
    @patch.object(CardProcessor, '_analyze_with_gemini')
    def test_edge_case_card_data_integration(self, mock_analyze):
        """Test workflow with edge case card data"""
        # Test with various edge cases in card data
        mock_analyze.return_value = json.dumps({
            "cards": [
                {
                    "name": "Unicode 测试用户",
                    "company": "国际公司 International Corp",
                    "title": "软件工程师 / Software Engineer",
                    "phone": "+86-138-0013-8000",
                    "email": "unicode.test@国际.com",
                    "address": "北京市朝阳区 / Beijing Chaoyang District",
                    "confidence_score": 0.9,
                    "quality_score": 0.8
                },
                {
                    "name": "Special-Chars",
                    "company": "O'Reilly & Co.",
                    "title": "VP of R&D",
                    "phone": "+1-555-123-4567 ext. 890",
                    "email": "special@o-reilly.co.uk",
                    "website": "https://www.o-reilly.co.uk/special-chars",
                    "confidence_score": 0.85,
                    "quality_score": 0.82
                }
            ]
        })
        
        image_data = self.create_test_image_bytes()
        cards = self.processor.process_image(image_data, self.test_user_id)
        
        assert len(cards) == 2
        
        # Verify Unicode handling
        assert cards[0].name == "Unicode 测试用户"
        assert "国际公司" in cards[0].company
        assert "北京市" in cards[0].address
        
        # Verify special characters handling
        assert cards[1].name == "Special-Chars"
        assert "O'Reilly & Co." == cards[1].company
        assert "VP of R&D" == cards[1].title